"""Dead letter queue — events that exceeded retry limit."""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg

from backend.accounting.db.pool import get_pool


async def send_to_dlq(event_id: str, reason: str) -> None:
    """Move an event to the dead letter queue (marks it with DLQ flag)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        await conn.execute(
            """UPDATE accounting.accounting_event SET
                processing_state = 'failed',
                last_error = $2,
                next_retry_at = NULL,
                updated_at = $3
               WHERE id = $1 AND is_current = true""",
            event_id,
            f"DLQ: {reason}",
            now,
        )


async def get_dlq_events(limit: int = 100) -> list[dict]:
    """Get events in the dead letter queue (failed with no retry)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, company_id, event_type, last_error, attempt_count, created_at
               FROM accounting.accounting_event
               WHERE processing_state = 'failed'
                 AND is_current = true
                 AND next_retry_at IS NULL
               ORDER BY updated_at DESC
               LIMIT $1""",
            limit,
        )
        return [dict(r) for r in rows]


async def reprocess_manually(event_id: str) -> bool:
    """Reset a DLQ'd event back to NEW for manual reprocessing."""
    from backend.accounting.orchestrator.event_dispatcher import transition_state
    from backend.accounting.models.enums import ProcessingState

    return await transition_state(event_id, ProcessingState.NEW, clear_decision=True)
