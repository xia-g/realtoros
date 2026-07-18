"""PostingEngine — orchestrates posting rules, generates deterministic postings.

Invariant: Posting = f(Decision, PostingRulesVersion)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import asyncpg

from backend.accounting.db.pool import get_pool
from backend.accounting.ledger.chart.accounts import seed_sql
from backend.accounting.ledger.posting.base import PostingResult


@dataclass
class PostedBatch:
    batch_id: str
    entry_id: str
    posting_hash: str
    lines: list
    total_debit: float
    total_credit: float


class PostingEngine:
    """Deterministic posting engine.

    Posting = f(Decision, PostingRulesVersion)
    """

    def __init__(self):
        from backend.accounting.ledger.posting.rules.sale_to_revenue import SaleToRevenue
        from backend.accounting.ledger.posting.rules.client_payment import ClientPayment
        from backend.accounting.ledger.posting.rules.expense_payment import ExpensePayment
        from backend.accounting.ledger.posting.rules.bank_transfer import BankTransfer
        from backend.accounting.ledger.posting.rules.manual_adjustment import ManualAdjustment

        self._rules = [
            SaleToRevenue(),
            ClientPayment(),
            ExpensePayment(),
            BankTransfer(),
            ManualAdjustment(),
        ]
        self._rules.sort(key=lambda r: -r.priority)

    async def evaluate(
        self,
        decision_id: str,
        posting_rules_version: str,
        company_id: str,
        trace_id: str | None = None,
    ) -> PostedBatch:
        """Evaluate decision and create ledger postings."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1. Load decision
            dec = await conn.fetchrow(
                """SELECT d.id, d.event_id, d.decision_version, d.ruleset_version,
                          d.included, d.reason,
                          e.event_type, e.amount, e.currency, e.company_id,
                          e.event_date
                   FROM accounting.accounting_decision d
                   JOIN accounting.accounting_event e ON e.id = d.event_id AND e.is_current = true
                   WHERE d.id = $1 AND d.superseded_at IS NULL""",
                decision_id,
            )
            if not dec or not dec["included"]:
                raise ValueError(f"Decision {decision_id} not included or not found")

            # 2. Load explanations
            expls = await conn.fetch(
                "SELECT rule_code, weight, message, payload_json FROM accounting.decision_explanation WHERE decision_id = $1",
                decision_id,
            )
            expl_list = [dict(r) for r in expls]

            # 3. Find applicable rule
            event_type = dec["event_type"]
            decision = dict(dec)
            result: PostingResult | None = None

            for rule in self._rules:
                if rule.supports(event_type, decision, expl_list):
                    result = rule.generate(event_type, decision, expl_list)
                    result.validate()
                    break

            if result is None:
                raise ValueError(f"No posting rule found for event_type={event_type}")

            # 4. Compute deterministic hash
            amount = float(decision["amount"])
            hash_input = {
                "event_type": event_type,
                "amount": str(amount),
                "currency": decision["currency"],
                "posting_rules_version": posting_rules_version,
                "lines": [(l.account_code, l.direction, l.amount) for l in result.lines],
            }
            posting_hash = hashlib.sha256(
                json.dumps(hash_input, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()

            # 5. Create posting batch + ledger entry + lines (in transaction)
            batch_id = str(uuid.uuid4())
            entry_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            entry_date = decision["event_date"].date() if hasattr(decision["event_date"], "date") else date.today()

            await conn.execute(
                """INSERT INTO accounting.posting_batch
                   (id, company_id, decision_id, posting_rules_version, status, total_debit, total_credit, is_closed, created_at)
                   VALUES ($1,$2,$3,$4,'completed',$5,$6,false,now())""",
                batch_id, company_id, decision_id, posting_rules_version,
                sum(l.amount for l in result.lines if l.direction == "debit"),
                sum(l.amount for l in result.lines if l.direction == "credit"),
            )

            # Resolve period — every line must belong to exactly one tax period
            period = await conn.fetchrow(
                """SELECT id FROM accounting.tax_period
                   WHERE company_id = $1 AND date_from <= $2 AND date_to >= $2
                   AND status = 'open' LIMIT 1""",
                company_id, entry_date,
            )
            if not period:
                raise ValueError(
                    f"No open tax period found for company {company_id} on {entry_date}. "
                    "Every ledger line must belong to exactly one tax period."
                )

            await conn.execute(
                """INSERT INTO accounting.ledger_entry
                   (id, batch_id, company_id, period_id, entry_date, description,
                    is_reversal, posting_hash, created_by, trace_id, created_at)
                   VALUES ($1,$2,$3,$4,$5,$6,false,$7,$8,$9,now())""",
                entry_id, batch_id, company_id,
                period["id"],
                entry_date,
                f"Posting for decision {decision_id}: {event_type} {amount:,.2f}",
                posting_hash, decision.get("created_by"), trace_id,
            )

            for line in result.lines:
                await conn.execute(
                    """INSERT INTO accounting.ledger_line
                       (id, entry_id, account_code, direction, amount, currency, created_at)
                       VALUES ($1,$2,$3,$4,$5,$6,now())""",
                    str(uuid.uuid4()), entry_id, line.account_code, line.direction,
                    line.amount, line.currency,
                )

            # Posting decision link
            await conn.execute(
                """INSERT INTO accounting.posting_decision_link
                   (id, decision_id, batch_id, posting_rule_code, posting_rule_version, decision_version, created_at)
                   VALUES ($1,$2,$3,$4,$5,$6,now())""",
                str(uuid.uuid4()), decision_id, batch_id,
                result.rule_code, posting_rules_version, decision["decision_version"],
            )

            return PostedBatch(
                batch_id=batch_id,
                entry_id=entry_id,
                posting_hash=posting_hash,
                lines=[{"account": l.account_code, "direction": l.direction, "amount": l.amount} for l in result.lines],
                total_debit=sum(l.amount for l in result.lines if l.direction == "debit"),
                total_credit=sum(l.amount for l in result.lines if l.direction == "credit"),
            )

    async def seed_chart(self) -> None:
        """Seed chart of accounts (idempotent)."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            from backend.accounting.ledger.chart.accounts import seed_sql
            await conn.execute(seed_sql())
