"""Audit logger for accounting decisions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import json

import asyncpg

from backend.accounting.db.pool import get_pool

logger = logging.getLogger("accounting.audit")


async def log_decision(
    event_id: str,
    decision_id: str,
    action: str,
    actor_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Log an audit entry for decision changes."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO accounting.accounting_decision_audit
               (event_id, decision_id, action, actor_id, details, created_at)
               VALUES ($1, $2, $3, $4, $5::jsonb, now())""",
            event_id,
            decision_id,
            action,
            actor_id,
            json.dumps(details or {}) if details else "{}",
        )
    logger.info(
        "audit_decision",
        extra={"event_id": event_id, "decision_id": decision_id, "action": action, "actor_id": actor_id},
    )


# Note: accounting_decision_audit table to be created in a future migration.
# For now, audit is logged via structured logging only.
async def log_decision_structured(
    event_id: str,
    decision_id: str,
    action: str,
    actor_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Structured logging fallback for audit (no table dependency)."""
    logger.info(
        "audit",
        extra={
            "event_id": event_id,
            "decision_id": decision_id,
            "action": action,
            "actor_id": actor_id,
            "details": details or {},
        },
    )
