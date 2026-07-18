"""Orchestrator — event pipeline state transitions.

Manages: NEW → RECOGNIZING → READY_FOR_DECISION → DECIDING → DONE / FAILED
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import asyncpg

from backend.accounting.db.pool import get_pool
from backend.accounting.models.enums import ProcessingState


async def transition_state(
    event_id: str,
    new_state: ProcessingState,
    error: str | None = None,
    clear_decision: bool = False,
) -> bool:
    """Move an event to a new processing state. Returns True if successful."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Prevent stale transitions — only allow valid path
        allowed = {
            ProcessingState.NEW: [ProcessingState.RECOGNIZING, ProcessingState.FAILED],
            ProcessingState.RECOGNIZING: [ProcessingState.READY_FOR_DECISION, ProcessingState.FAILED],
            ProcessingState.READY_FOR_DECISION: [ProcessingState.DECIDING, ProcessingState.FAILED],
            ProcessingState.DECIDING: [ProcessingState.DONE, ProcessingState.FAILED],
            ProcessingState.FAILED: [ProcessingState.RECOGNIZING, ProcessingState.READY_FOR_DECISION, ProcessingState.DECIDING],
        }

        # Get current state
        row = await conn.fetchrow(
            "SELECT processing_state FROM accounting.accounting_event WHERE id = $1 AND is_current = true",
            event_id
        )
        if not row:
            return False

        current = ProcessingState(row["processing_state"])
        if new_state not in allowed.get(current, []):
            # Allow DONE/FAILED from DECIDING
            if current == ProcessingState.DECIDING and new_state in (ProcessingState.DONE, ProcessingState.FAILED):
                pass
            elif current == ProcessingState.FAILED and new_state in (ProcessingState.RECOGNIZING, ProcessingState.READY_FOR_DECISION, ProcessingState.DECIDING):
                pass
            else:
                return False

        now = datetime.now(timezone.utc)
        if new_state == ProcessingState.FAILED:
            attempt = await conn.fetchval(
                "SELECT attempt_count FROM accounting.accounting_event WHERE id = $1",
                event_id
            ) or 0
            await conn.execute(
                """UPDATE accounting.accounting_event SET
                    processing_state = $2, last_error = $3, attempt_count = $4,
                    next_retry_at = $5, updated_at = $6
                   WHERE id = $1 AND is_current = true""",
                event_id, new_state.value, error, attempt + 1,
                now, now
            )
        elif new_state == ProcessingState.DONE and clear_decision:
            await conn.execute(
                """UPDATE accounting.accounting_event SET
                    processing_state = $2, decision_state = 'pending',
                    updated_at = $3 WHERE id = $1 AND is_current = true""",
                event_id, new_state.value, now
            )
        else:
            await conn.execute(
                "UPDATE accounting.accounting_event SET processing_state = $2, updated_at = $3 WHERE id = $1 AND is_current = true",
                event_id, new_state.value, now
            )
        return True


async def set_ready_for_decision(event_id: str) -> bool:
    """Mark event as ready for decision engine (after recognition)."""
    return await transition_state(event_id, ProcessingState.READY_FOR_DECISION)


async def mark_failed(event_id: str, error: str) -> bool:
    """Mark event as failed with error message."""
    return await transition_state(event_id, ProcessingState.FAILED, error=error)


async def reset_failed(event_id: str) -> bool:
    """Reset a failed event back to NEW for reprocessing."""
    return await transition_state(event_id, ProcessingState.NEW)


async def get_next_batch(processing_state: ProcessingState, limit: int = 100) -> list[dict]:
    """Get events ready for the next processing stage.

    For FAILED events, only returns those past their retry time.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if processing_state == ProcessingState.FAILED:
            rows = await conn.fetch(
                """SELECT id, company_id, event_type, event_fingerprint
                   FROM accounting.accounting_event
                   WHERE processing_state = 'failed' AND is_current = true
                   AND (next_retry_at IS NULL OR next_retry_at <= now())
                   ORDER BY attempt_count, next_retry_at
                   LIMIT $1""",
                limit
            )
        else:
            rows = await conn.fetch(
                """SELECT id, company_id, event_type, event_fingerprint
                   FROM accounting.accounting_event
                   WHERE processing_state = $1 AND is_current = true
                   ORDER BY created_at
                   LIMIT $2""",
                processing_state.value, limit
            )
        return [dict(r) for r in rows]
