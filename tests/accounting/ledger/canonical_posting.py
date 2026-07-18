"""Canonical posting representation — deterministic output of PostingEngine.

This is a PROTOCOL definition, NOT the real Posting Engine.

PostingEngine (to be built in Phase 3) MUST produce the same output
as canonical_posting() for the same inputs.

Invariant:
    canonical_posting(A, V) ≡ canonical_posting(A, V)
    for all A (decision) and V (rules_version)

The real PostingEngine = f(Decision, PostingRulesVersion)
must produce the same canonical form.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any

import asyncpg

from backend.accounting.db.pool import get_pool


@dataclass(frozen=True)
class PostingLine:
    """A single posting line — deterministic representation."""
    account_code: str
    direction: str  # debit | credit
    amount: str     # stringified to avoid float precision issues
    currency: str = "RUB"


@dataclass(frozen=True)
class Posting:
    """A complete posting — fully deterministic."""
    decision_id: str
    decision_version: int
    ruleset_version: str
    posting_rules_version: str
    event_type: str | None
    amount: str
    lines: tuple[PostingLine, ...] = field(default_factory=tuple)

    def canonical_dict(self) -> dict[str, Any]:
        """Return a dict excluding all non-deterministic fields.

        decision_version is deliberately excluded: replay creates a new version,
        but the posting content (accounts, amounts, directions) must be identical.
        """
        return {
            "ruleset_version": self.ruleset_version,
            "posting_rules_version": self.posting_rules_version,
            "event_type": self.event_type,
            "amount": self.amount,
            "lines": sorted(
                [asdict(l) for l in self.lines],
                key=lambda x: (x["account_code"], x["direction"]),
            ),
        }

    def hash(self) -> str:
        """SHA256 of canonical representation — excludes ids, timestamps, trace_id."""
        raw = json.dumps(self.canonical_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()


async def canonical_posting(decision_id: str, rules_version: str | None = None) -> Posting:
    """Generate the canonical posting for a decision.

    This is a STUB that simulates what PostingEngine will produce.
    The real PostingEngine (Phase 3) MUST produce identical output
    for the same inputs.

    Args:
        decision_id: accounting_decision.id
        rules_version: posting_rules_version string (e.g. "2026.08.01")

    Returns:
        Posting — fully deterministic representation
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Load decision
        decision = await conn.fetchrow(
            """SELECT d.id, d.event_id, d.decision_version, d.ruleset_version,
                      d.included, d.reason,
                      e.event_type, e.amount, e.currency
               FROM accounting.accounting_decision d
               JOIN accounting.accounting_event e ON e.id = d.event_id AND e.is_current = true
               WHERE d.id = $1 AND d.superseded_at IS NULL""",
            decision_id,
        )
        if not decision:
            raise ValueError(f"Decision {decision_id} not found or superseded")
        if not decision["included"]:
            raise ValueError(f"Decision {decision_id} is not included — no posting expected")

        # 2. Load explanations (affects posting rules selection)
        explanations = await conn.fetch(
            "SELECT rule_code, weight, message FROM accounting.decision_explanation WHERE decision_id = $1",
            decision_id,
        )

        # 3. Deterministic posting rules dispatch
        event_type = decision["event_type"]
        amount = float(decision["amount"])
        currency = decision["currency"]
        rules_ver = rules_version or decision["ruleset_version"]

        lines = await _generate_lines(event_type, amount, currency, explanations)

        return Posting(
            decision_id=decision_id,
            decision_version=decision["decision_version"],
            ruleset_version=decision["ruleset_version"],
            posting_rules_version=rules_ver,
            event_type=event_type,
            amount=str(amount),
            lines=tuple(lines),
        )


async def _generate_lines(
    event_type: str,
    amount: float,
    currency: str,
    explanations: list[asyncpg.Record],
) -> list[PostingLine]:
    """Deterministic posting rule dispatch.

    These rules are a STUB of what PostingEngine will implement.
    They MUST be deterministic — same inputs → same lines.
    """
    lines: list[PostingLine] = []

    if event_type in ("sale", "client_payment"):
        # Revenue recognition
        lines.append(PostingLine(account_code="62", direction="debit", amount=str(amount), currency=currency))
        lines.append(PostingLine(account_code="90.01", direction="credit", amount=str(amount), currency=currency))
        # VAT accrual (20%)
        vat = round(amount * 20 / 120, 2)
        lines.append(PostingLine(account_code="90.03", direction="debit", amount=str(vat), currency=currency))
        lines.append(PostingLine(account_code="68", direction="credit", amount=str(vat), currency=currency))

    elif event_type in ("purchase", "agent_commission"):
        # Expense recognition
        lines.append(PostingLine(account_code="44", direction="debit", amount=str(amount), currency=currency))
        lines.append(PostingLine(account_code="60", direction="credit", amount=str(amount), currency=currency))

    elif event_type in ("bank_inflow",):
        # Cash inflow
        lines.append(PostingLine(account_code="51", direction="debit", amount=str(amount), currency=currency))
        lines.append(PostingLine(account_code="62", direction="credit", amount=str(amount), currency=currency))

    elif event_type in ("bank_outflow",):
        # Cash outflow
        lines.append(PostingLine(account_code="60", direction="debit", amount=str(amount), currency=currency))
        lines.append(PostingLine(account_code="51", direction="credit", amount=str(amount), currency=currency))

    else:
        # Default: dual-entry with suspense account
        lines.append(PostingLine(account_code="76", direction="debit", amount=str(amount), currency=currency))
        lines.append(PostingLine(account_code="76", direction="credit", amount=str(amount), currency=currency))

    # Sort for deterministic ordering
    lines.sort(key=lambda l: (l.account_code, l.direction))
    return lines


async def posting_hash(decision_id: str, rules_version: str | None = None) -> str:
    """SHA256 hash of canonical posting — excludes ids, timestamps, trace_id."""
    posting = await canonical_posting(decision_id, rules_version)
    return posting.hash()


async def batch_ledger_hash(decision_ids: list[str], rules_version: str | None = None) -> str:
    """Aggregate hash for a batch of postings — order-independent."""
    hashes = []
    for did in decision_ids:
        h = await posting_hash(did, rules_version)
        hashes.append(h)
    hashes.sort()
    combined = "|".join(hashes)
    return hashlib.sha256(combined.encode()).hexdigest()
