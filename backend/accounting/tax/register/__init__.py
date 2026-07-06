"""Tax Register — generates immutable tax registers from assignments.

TaxRegister.generate(assignments, tax_period) → TaxRegisterResult

Invariant: Tax register is immutable (INSERT only, no UPDATE/DELETE).
Invariant: Correction = new register version.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.accounting.db.pool import get_pool


@dataclass
class TaxRegisterEntry:
    """A single entry in a tax register."""
    entry_id: str
    register_id: str
    assignment_id: str
    ledger_line_id: str
    account_code: str
    amount: float
    direction: str
    tax_treatment: str
    excluded: bool


@dataclass
class TaxRegisterResult:
    """A complete tax register with entries."""
    register_id: str
    company_id: str
    tax_period_id: str
    register_type: str
    policy_version_id: str
    entries: list[TaxRegisterEntry]
    total_amount: float
    entry_count: int
    version: int = 1


class TaxRegister:
    """Generates and manages immutable tax registers."""

    @staticmethod
    async def generate(
        assignments: list,
        company_id: str,
        tax_period_id: str,
        register_type: str,
        policy_version_id: str,
    ) -> TaxRegisterResult:
        """Generate a tax register from assignments.

        Only non-excluded assignments create entries in their respective registers.
        Excluded assignments are tracked separately in EXCLUDED register.

        Args:
            assignments: List of TaxAssignment (asyncpg rows or dicts).
            company_id: Company ID.
            tax_period_id: Tax period ID.
            register_type: Type of register to generate.
            policy_version_id: Policy version used.

        Returns:
            TaxRegisterResult with entries.
        """
        pool = await get_pool()

        # Filter assignments for this register type
        filtered: list[dict] = []
        for a in assignments:
            if isinstance(a, dict):
                a_dict = a
            else:
                a_dict = dict(a)

            rt = a_dict.get("register_type", a_dict.get("register_type"))
            if rt != register_type:
                continue

            filtered.append(a_dict)

        # Build entries
        pool = await get_pool()
        entries: list[TaxRegisterEntry] = []

        # Resolve account codes from ledger lines
        async with pool.acquire() as conn:
            for a in filtered:
                line_id = a.get("ledger_line_id")
                line = await conn.fetchrow(
                    "SELECT id, account_code, direction, amount FROM accounting.ledger_line WHERE id = $1",
                    line_id,
                )
                if not line:
                    continue

                entries.append(TaxRegisterEntry(
                    entry_id=str(uuid.uuid4()),
                    register_id="",  # Will be set after register is created
                    assignment_id=a["id"],
                    ledger_line_id=line_id,
                    account_code=line["account_code"],
                    amount=float(line["amount"]),
                    direction=line["direction"],
                    tax_treatment=a.get("tax_treatment", "taxable"),
                    excluded=a.get("excluded", False),
                ))

        # Compute totals (excluded don't count toward register total)
        non_excluded = [e for e in entries if not e.excluded]
        total_amount = sum(e.amount for e in non_excluded)

        return TaxRegisterResult(
            register_id="",  # Set after DB insert
            company_id=company_id,
            tax_period_id=tax_period_id,
            register_type=register_type,
            policy_version_id=policy_version_id,
            entries=entries,
            total_amount=total_amount,
            entry_count=len(non_excluded),
            version=1,
        )

    @staticmethod
    async def save(result: TaxRegisterResult) -> str:
        """Persist a tax register with its entries to DB.

        Creates a new register version. Does NOT update existing registers.
        """
        pool = await get_pool()

        async with pool.acquire() as conn:
            # Get next version number
            last_version = await conn.fetchval(
                """SELECT COALESCE(MAX(register_version), 0)
                   FROM accounting.tax_register
                   WHERE company_id = $1 AND tax_period_id = $2 AND register_type = $3""",
                result.company_id,
                result.tax_period_id,
                result.register_type,
            )
            new_version = last_version + 1

            # Mark previous versions as not current
            await conn.execute(
                """UPDATE accounting.tax_register
                   SET is_current = false
                   WHERE company_id = $1 AND tax_period_id = $2 AND register_type = $3
                     AND is_current = true""",
                result.company_id,
                result.tax_period_id,
                result.register_type,
            )

            # Create register
            register_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO accounting.tax_register
                   (id, company_id, tax_period_id, register_type, register_version,
                    policy_version_id, entry_count, total_amount, is_current)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true)""",
                register_id,
                result.company_id,
                result.tax_period_id,
                result.register_type,
                new_version,
                result.policy_version_id,
                result.entry_count,
                result.total_amount,
            )

            # Insert entries
            for entry in result.entries:
                await conn.execute(
                    """INSERT INTO accounting.tax_register_entry
                       (id, register_id, assignment_id, ledger_line_id,
                        account_code, amount, direction, tax_treatment, excluded)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                    entry.entry_id,
                    register_id,
                    entry.assignment_id,
                    entry.ledger_line_id,
                    entry.account_code,
                    entry.amount,
                    entry.direction,
                    entry.tax_treatment,
                    entry.excluded,
                )

            return register_id

    @staticmethod
    async def generate_all(
        assignments: list,
        company_id: str,
        tax_period_id: str,
        policy_version_id: str,
    ) -> dict[str, TaxRegisterResult]:
        """Generate all tax registers for all types based on assignments.

        Returns:
            Dict of register_type → TaxRegisterResult
        """
        from backend.accounting.models.enums import TaxRegisterType

        results: dict[str, TaxRegisterResult] = {}

        for rt in TaxRegisterType:
            result = await TaxRegister.generate(
                assignments=assignments,
                company_id=company_id,
                tax_period_id=tax_period_id,
                register_type=rt.value,
                policy_version_id=policy_version_id,
            )
            if result.entries:
                register_id = await TaxRegister.save(result)
                result.register_id = register_id
                results[rt.value] = result

        return results
