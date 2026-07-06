"""Tax Assignment Engine — maps ledger lines to tax registers.

TaxAssignmentEngine.assign(ledger_line, tax_policy_version) → TaxAssignment

Invariant: One ledger_line → exactly one active (is_current=true) assignment.
Invariant: Tax = f(Ledger, TaxPolicyVersion) — NOT LedgerLine.tax_register_id.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.accounting.db.pool import get_pool
from backend.accounting.tax.policy import TaxPolicy, TaxPolicyVersionInfo, TaxRuleMatch
from backend.accounting.models.enums import TaxReasonCode


@dataclass
class TaxAssignment:
    """Result of tax assignment — maps a ledger line to a tax register."""
    assignment_id: str
    ledger_line_id: str
    company_id: str
    policy_version_id: str
    register_type: str
    tax_treatment: str
    excluded: bool
    reason_code: str | None
    is_current: bool = True
    version: int = 1


class TaxAssignmentEngine:
    """Maps ledger lines to tax registers deterministically.

    Pure function:
        assign(ledger_line, tax_policy_version) → TaxAssignment

    Does NOT mutate ledger, does NOT write to ledger_line.
    """

    def __init__(self):
        self._policy = TaxPolicy()

    async def assign(
        self,
        ledger_line: dict[str, Any] | None = None,
        ledger_line_id: str | None = None,
        company_id: str | None = None,
        policy_version: TaxPolicyVersionInfo | None = None,
        account_code: str | None = None,
        direction: str | None = None,
        trace_id: str | None = None,
    ) -> TaxAssignment:
        """Assign a ledger line to a tax register.

        Args:
            Either pass a full ledger_line dict, OR individual params.

        Returns:
            TaxAssignment with mapping to tax register.
        """
        # Resolve inputs
        if ledger_line:
            ll_id = ledger_line["id"]
            ll_account = ledger_line["account_code"]
            ll_direction = ledger_line["direction"]
            ll_company = ledger_line.get("company_id", company_id)
            # ledger_line doesn't directly have company_id — infer from entry
            if not ll_company:
                ll_company = company_id
        else:
            ll_id = ledger_line_id
            ll_account = account_code
            ll_direction = direction
            ll_company = company_id

        if not ll_id or not ll_account or not ll_direction:
            raise ValueError("ledger_line_id, account_code, and direction are required")

        # Evaluate tax policy
        match = self._policy.evaluate(ll_account, ll_direction, policy_version)

        # Build assignment
        if match.matched and match.rule:
            assignment = TaxAssignment(
                assignment_id=str(uuid.uuid4()),
                ledger_line_id=ll_id,
                company_id=ll_company or "",
                policy_version_id=policy_version.policy_version_id if policy_version else "",
                register_type=match.rule.register_type,
                tax_treatment=match.rule.tax_treatment,
                excluded=match.rule.excluded,
                reason_code=match.reason_code,
                is_current=True,
                version=1,
            )
        else:
            # Default exclusion — no matching rule
            assignment = TaxAssignment(
                assignment_id=str(uuid.uuid4()),
                ledger_line_id=ll_id,
                company_id=ll_company or "",
                policy_version_id=policy_version.policy_version_id if policy_version else "",
                register_type="EXCLUDED",
                tax_treatment="excluded",
                excluded=True,
                reason_code=match.reason_code or TaxReasonCode.UNMAPPED_ACCOUNT.value,
                is_current=True,
                version=1,
            )

        return assignment

    async def assign_and_save(
        self,
        ledger_line: dict[str, Any],
        entry_id: str,
        company_id: str,
        policy_version: TaxPolicyVersionInfo | None = None,
        trace_id: str | None = None,
    ) -> TaxAssignment:
        """Assign a ledger line and persist to DB."""
        assignment = await self.assign(
            ledger_line=ledger_line,
            company_id=company_id,
            policy_version=policy_version,
            trace_id=trace_id,
        )

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO accounting.tax_assignment
                   (id, ledger_line_id, ledger_entry_id, company_id,
                    policy_version_id, register_type, tax_treatment,
                    excluded, reason_code, is_current, version)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, true, 1)""",
                assignment.assignment_id,
                assignment.ledger_line_id,
                entry_id,
                company_id,
                assignment.policy_version_id,
                assignment.register_type,
                assignment.tax_treatment,
                assignment.excluded,
                assignment.reason_code,
            )

        return assignment

    async def assign_entry_lines(
        self,
        entry_id: str,
        company_id: str,
        policy_version: TaxPolicyVersionInfo | None = None,
        trace_id: str | None = None,
    ) -> list[TaxAssignment]:
        """Assign ALL ledger lines of an entry to tax registers."""
        pool = await get_pool()
        assignments: list[TaxAssignment] = []

        async with pool.acquire() as conn:
            lines = await conn.fetch(
                "SELECT id, account_code, direction, amount FROM accounting.ledger_line WHERE entry_id = $1",
                entry_id,
            )

        for line in lines:
            ll_dict = {
                "id": str(line["id"]),
                "account_code": line["account_code"],
                "direction": line["direction"],
                "amount": float(line["amount"]),
            }
            assignment = await self.assign_and_save(
                ledger_line=ll_dict,
                entry_id=entry_id,
                company_id=company_id,
                policy_version=policy_version,
                trace_id=trace_id,
            )
            assignments.append(assignment)

        return assignments
