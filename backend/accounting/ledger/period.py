"""Period lock service — open/close periods, validate posting permissions."""

from __future__ import annotations

from datetime import date, datetime, timezone

from backend.accounting.db.pool import get_pool


async def close_period(period_id: str, actor_id: str | None = None) -> bool:
    """Close a tax period — postings are forbidden after this."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE accounting.tax_period SET status = 'closed' WHERE id = $1 AND status = 'open'",
            period_id,
        )
        return result != "UPDATE 0"


async def lock_period(period_id: str, actor_id: str | None = None) -> bool:
    """Lock a period — only review allowed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE accounting.tax_period SET status = 'locked' WHERE id = $1 AND status = 'open'",
            period_id,
        )
        return result != "UPDATE 0"


async def open_period(period_id: str, actor_id: str | None = None) -> bool:
    """Re-open a locked period."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE accounting.tax_period SET status = 'open' WHERE id = $1 AND status IN ('locked', 'closed')",
            period_id,
        )
        return result != "UPDATE 0"


async def find_open_period(company_id: str, entry_date: date) -> str | None:
    """Find an open period for a given date. Returns period_id or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id FROM accounting.tax_period
               WHERE company_id = $1 AND date_from <= $2 AND date_to >= $2
               AND status = 'open' LIMIT 1""",
            company_id, entry_date,
        )
        return str(row["id"]) if row else None


async def is_period_closed(period_id: str) -> bool:
    """Check if a period is closed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM accounting.tax_period WHERE id = $1",
            period_id,
        )
        return status == "closed"
