"""Database helpers — dedup check, connection helpers."""

from __future__ import annotations

import asyncpg

from backend.accounting.db.pool import get_pool


async def check_fingerprint_unique(company_id: str, fingerprint: str) -> bool:
    """Check if a fingerprint already exists. Returns True if unique."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            """SELECT 1 FROM accounting.accounting_event
               WHERE company_id = $1 AND event_fingerprint = $2 AND is_current = true
               LIMIT 1""",
            company_id,
            fingerprint,
        )
        return row is None


async def check_source_unique(source_system: str, source_type: str, source_id: str, event_type: str) -> bool:
    """Check if a source is already linked to an active event."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            """SELECT 1 FROM accounting.accounting_event
               WHERE source_system = $1 AND source_type = $2 AND source_id = $3
                 AND event_type = $4 AND is_current = true
               LIMIT 1""",
            source_system,
            source_type,
            source_id,
            event_type,
        )
        return row is None
