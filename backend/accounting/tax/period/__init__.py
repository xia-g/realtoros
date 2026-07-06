"""Tax Period Mapping — resolves tax periods from accounting periods.

TaxPeriodResolver resolves the relationship between accounting periods
(monthly) and tax periods (quarterly/yearly depending on regime).

Invariant: Ledger_period != Tax_period
Invariant: Many accounting periods → one tax period.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.accounting.db.pool import get_pool


@dataclass
class TaxPeriodInfo:
    """Resolved tax period information."""
    tax_period_id: str
    date_from: date
    date_to: date
    period_type: str  # month, quarter, year
    status: str       # open, locked, closed
    accounting_period_ids: list[str]


class TaxPeriodResolver:
    """Resolves tax periods from accounting periods.

    Supports month, quarter, and year tax periods.
    """

    @staticmethod
    def get_period_type_for_regime(tax_regime: str) -> str:
        """Get tax period type for a tax regime."""
        mapping = {
            "usn_income": "year",
            "usn_income_expense": "year",
            "osno": "quarter",
            "psn": "year",
        }
        return mapping.get(tax_regime, "quarter")

    @staticmethod
    async def find_or_create_period(
        company_id: str,
        target_date: date,
        period_type: str | None = None,
    ) -> TaxPeriodInfo:
        """Find or create a tax period for a target date.

        Args:
            company_id: Company ID.
            target_date: Date to resolve period for.
            period_type: 'month', 'quarter', or 'year'.
                If None, resolved from company's tax regime.

        Returns:
            TaxPeriodInfo with period details.
        """
        pool = await get_pool()

        # Resolve period_type if not given
        if period_type is None:
            async with pool.acquire() as conn:
                regime_row = await conn.fetchrow(
                    "SELECT regime_type::text FROM accounting.tax_regime WHERE company_id = $1 AND is_active = true",
                    company_id,
                )
                if regime_row:
                    period_type = TaxPeriodResolver.get_period_type_for_regime(regime_row["regime_type"])
                else:
                    period_type = "quarter"

        # Compute period boundaries
        date_from, date_to = TaxPeriodResolver.compute_period_bounds(target_date, period_type)

        # Find existing period
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, date_from, date_to, period_type, status
                   FROM accounting.tax_period
                   WHERE company_id = $1 AND date_from = $2 AND date_to = $3
                   LIMIT 1""",
                company_id,
                date_from,
                date_to,
            )

            if row:
                return TaxPeriodInfo(
                    tax_period_id=str(row["id"]),
                    date_from=row["date_from"],
                    date_to=row["date_to"],
                    period_type=row["period_type"],
                    status=row["status"],
                    accounting_period_ids=[],
                )

            # Create new period
            import uuid
            period_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO accounting.tax_period
                   (id, company_id, date_from, date_to, period_type, status)
                   VALUES ($1, $2, $3, $4, $5, 'open')""",
                period_id,
                company_id,
                date_from,
                date_to,
                period_type,
            )

            return TaxPeriodInfo(
                tax_period_id=period_id,
                date_from=date_from,
                date_to=date_to,
                period_type=period_type,
                status="open",
                accounting_period_ids=[],
            )

    @staticmethod
    def compute_period_bounds(target_date: date, period_type: str) -> tuple[date, date]:
        """Compute period start and end dates for a period type."""
        if period_type == "month":
            import calendar
            last_day = calendar.monthrange(target_date.year, target_date.month)[1]
            return (
                date(target_date.year, target_date.month, 1),
                date(target_date.year, target_date.month, last_day),
            )
        elif period_type == "quarter":
            quarter = (target_date.month - 1) // 3
            q_start = date(target_date.year, quarter * 3 + 1, 1)
            q_end_month = quarter * 3 + 3
            if q_end_month == 12:
                q_end = date(target_date.year, 12, 31)
            else:
                import calendar
                q_end = date(target_date.year, q_end_month, calendar.monthrange(target_date.year, q_end_month)[1])
            return (q_start, q_end)
        elif period_type == "year":
            return (
                date(target_date.year, 1, 1),
                date(target_date.year, 12, 31),
            )
        else:
            raise ValueError(f"Unknown period_type: {period_type}")

    @staticmethod
    async def can_close_tax_period(tax_period_id: str) -> dict[str, Any]:
        """Check if a tax period can be closed.

        All underlying accounting periods must be closed.
        All ledger lines must have assignments.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            period = await conn.fetchrow(
                "SELECT * FROM accounting.tax_period WHERE id = $1",
                tax_period_id,
            )
            if not period:
                return {"can_close": False, "reason": "Period not found"}

            if period["status"] == "closed":
                return {"can_close": True, "reason": "Already closed"}

            # Check: all ledger lines have tax assignments
            unassigned = await conn.fetchval(
                """SELECT count(*) FROM accounting.ledger_line ll
                   JOIN accounting.ledger_entry le ON le.id = ll.entry_id
                   WHERE le.period_id = $1
                     AND NOT EXISTS (
                         SELECT 1 FROM accounting.tax_assignment ta
                         WHERE ta.ledger_line_id = ll.id AND ta.is_current = true
                     )""",
                tax_period_id,
            )

            if unassigned and unassigned > 0:
                return {
                    "can_close": False,
                    "reason": f"{unassigned} ledger lines have no tax assignment",
                }

            return {"can_close": True, "reason": "Ready to close"}

    @staticmethod
    async def close_tax_period(tax_period_id: str) -> bool:
        """Close a tax period if all checks pass."""
        check = await TaxPeriodResolver.can_close_tax_period(tax_period_id)
        if not check["can_close"]:
            return False

        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE accounting.tax_period SET status = 'closed' WHERE id = $1 AND status <> 'closed'",
                tax_period_id,
            )
            return "UPDATE 1" in str(result)
