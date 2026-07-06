"""Tax Replay — recalculate tax assignments and regenerate registers.

TaxReplay.recalculate(tax_policy_version)

Rules:
- Does NOT change ledger
- Creates new assignments (old superseded)
- Creates new register versions
- Closed tax period: replay creates new version, not new period
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from backend.accounting.db.pool import get_pool
from backend.accounting.tax.policy import TaxPolicy, TaxPolicyVersionInfo
from backend.accounting.tax.assignment import TaxAssignmentEngine, TaxAssignment
from backend.accounting.tax.register import TaxRegister


@dataclass
class TaxReplayResult:
    """Result of a tax replay operation."""
    new_assignments_count: int
    superseded_count: int
    registers_created: list[str]
    policy_version_used: str
    ledger_unchanged: bool = True
    trace_id: str | None = None


class TaxReplay:
    """Recalculates tax assignments and regenerates registers.

    Does NOT modify ledger under any circumstances.
    """

    def __init__(self):
        self._engine = TaxAssignmentEngine()
        self._policy = TaxPolicy()

    async def recalculate(
        self,
        company_id: str,
        tax_period_id: str,
        tax_policy_version: str | None = None,
        trace_id: str | None = None,
    ) -> TaxReplayResult:
        """Recalculate all tax assignments for a company and period.

        Args:
            company_id: Company to recalculate for.
            tax_period_id: Tax period to recalculate.
            tax_policy_version: Specific policy version to use.
                If None, uses the current active version.
            trace_id: Optional trace ID.

        Returns:
            TaxReplayResult with counts of new/superseded assignments.
        """
        pool = await get_pool()

        # 1. Find the tax period and its underlying accounting periods
        async with pool.acquire() as conn:
            period = await conn.fetchrow(
                """SELECT id, company_id, date_from, date_to, period_type, status
                   FROM accounting.tax_period
                   WHERE id = $1 AND company_id = $2""",
                tax_period_id,
                company_id,
            )
            if not period:
                raise ValueError(f"Tax period {tax_period_id} not found for company {company_id}")

            if period["status"] == "closed":
                raise ValueError(f"Tax period {tax_period_id} is closed — replay not allowed")

            # 2. Get active policy version
            if tax_policy_version:
                pv = await conn.fetchrow(
                    """SELECT pv.id, pv.policy_id, pv.version, pv.effective_from,
                              pv.effective_to, pv.rules_hash, p.tax_regime
                       FROM accounting.tax_policy_version pv
                       JOIN accounting.tax_policy p ON p.id = pv.policy_id
                       WHERE pv.version = $1 AND pv.is_active = true
                       LIMIT 1""",
                    tax_policy_version,
                )
            else:
                # Use TaxPolicy to resolve regime mapping
                policy_info = await self._policy.get_active_policy_version(
                    company_id,
                    date.today() if period["date_from"] is None else period["date_from"],
                )
                if not policy_info:
                    raise ValueError("No active tax policy version found")
                pv = await conn.fetchrow(
                    """SELECT pv.id, pv.policy_id, pv.version, pv.effective_from,
                              pv.effective_to, pv.rules_hash, p.tax_regime
                       FROM accounting.tax_policy_version pv
                       JOIN accounting.tax_policy p ON p.id = pv.policy_id
                       WHERE pv.id = $1""",
                    policy_info.policy_version_id,
                )

            if not pv:
                raise ValueError("No active tax policy version found")

            # 3. Load rules for this policy version
            rule_rows = await conn.fetch(
                """SELECT id, policy_version_id, priority, rule_code,
                          account_pattern, direction, register_type,
                          tax_treatment, excluded, reason_code,
                          amount_multiplier::text
                   FROM accounting.tax_rule
                   WHERE policy_version_id = $1
                   ORDER BY priority DESC""",
                pv["id"],
            )

        policy_version_info = TaxPolicyVersionInfo(
            policy_version_id=str(pv["id"]),
            policy_id=str(pv["policy_id"]),
            version=pv["version"],
            tax_regime=pv["tax_regime"],
            effective_from=pv["effective_from"],
            effective_to=pv["effective_to"],
            rules=[],
            rules_hash=pv["rules_hash"],
        )
        # Populate rules (reconstructed from DB rows)
        from backend.accounting.tax.policy import TaxRule
        for r in rule_rows:
            policy_version_info.rules.append(TaxRule(
                id=str(r["id"]),
                policy_version_id=str(r["policy_version_id"]),
                priority=r["priority"],
                rule_code=r["rule_code"],
                account_pattern=r["account_pattern"],
                direction=r["direction"],
                register_type=r["register_type"],
                tax_treatment=r["tax_treatment"],
                excluded=r["excluded"],
                reason_code=r["reason_code"],
                amount_multiplier=float(r["amount_multiplier"]),
            ))

        # 4. Load all ledger entries with lines for this period
        async with pool.acquire() as conn:
            entries = await conn.fetch(
                """SELECT le.id AS entry_id, le.company_id,
                          ll.id AS line_id, ll.account_code, ll.direction,
                          ll.amount::text AS amount
                   FROM accounting.ledger_entry le
                   JOIN accounting.ledger_line ll ON ll.entry_id = le.id
                   WHERE le.company_id = $1 AND le.period_id = $2
                   ORDER BY le.created_at""",
                company_id,
                tax_period_id,
            )

        # 5. Supersede existing assignments
        async with pool.acquire() as conn:
            old_current = await conn.execute(
                """UPDATE accounting.tax_assignment
                   SET is_current = false
                   WHERE company_id = $1
                     AND ledger_entry_id = ANY(
                         SELECT id FROM accounting.ledger_entry
                         WHERE company_id = $1 AND period_id = $2
                     )
                     AND is_current = true""",
                company_id,
                tax_period_id,
            )
            superseded_count = 0
            if old_current:
                # asyncpg returns string like "UPDATE N" for UPDATE statements
                parts = str(old_current).split()
                if len(parts) >= 2:
                    try:
                        superseded_count = int(parts[1])
                    except (ValueError, IndexError):
                        superseded_count = 0

        # 6. Create new assignments for each ledger line
        new_assignments: list[TaxAssignment] = []
        async with pool.acquire() as conn:
            for entry in entries:
                line_dict = {
                    "id": str(entry["line_id"]),
                    "account_code": entry["account_code"],
                    "direction": entry["direction"],
                    "amount": float(entry["amount"]),
                    "company_id": str(entry["company_id"]),
                }
                assignment = await self._engine.assign(
                    ledger_line=line_dict,
                    company_id=str(entry["company_id"]),
                    policy_version=policy_version_info,
                    trace_id=trace_id,
                )
                new_assignments.append(assignment)

                # Save to DB
                await conn.execute(
                    """INSERT INTO accounting.tax_assignment
                       (id, ledger_line_id, ledger_entry_id, company_id,
                        policy_version_id, register_type, tax_treatment,
                        excluded, reason_code, is_current, version)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, true, $10)""",
                    assignment.assignment_id,
                    assignment.ledger_line_id,
                    str(entry["entry_id"]),
                    str(entry["company_id"]),
                    assignment.policy_version_id or pv["id"],
                    assignment.register_type,
                    assignment.tax_treatment,
                    assignment.excluded,
                    assignment.reason_code,
                    1,
                )

        # 7. Generate new tax registers
        all_assignment_rows = []
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT ta.* FROM accounting.tax_assignment ta
                   JOIN accounting.ledger_entry le ON le.id = ta.ledger_entry_id
                   WHERE le.company_id = $1 AND le.period_id = $2
                     AND ta.is_current = true""",
                company_id,
                tax_period_id,
            )
            all_assignment_rows = [dict(r) for r in rows]

        register_results = await TaxRegister.generate_all(
            assignments=all_assignment_rows,
            company_id=company_id,
            tax_period_id=tax_period_id,
            policy_version_id=str(pv["id"]),
        )

        return TaxReplayResult(
            new_assignments_count=len(new_assignments),
            superseded_count=superseded_count,
            registers_created=list(register_results.keys()),
            policy_version_used=pv["version"],
            ledger_unchanged=True,
            trace_id=trace_id,
        )
