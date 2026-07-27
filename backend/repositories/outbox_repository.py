"""OutboxRepository — enqueue, poll, mark published/failed.

Uses psycopg2 directly (same pattern as DocumentRepository)
for transactional integration with domain entity saves.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from structlog import get_logger

from backend.core.integration_event import IntegrationEvent

logger = get_logger(__name__)


class OutboxRepository:
    """Repository for event_outbox table.

    Operates in the same transaction as domain entity updates.
    Uses raw SQL via psycopg2 for precise transaction control.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(self._dsn)

    def enqueue(self, event: IntegrationEvent, conn=None) -> None:
        """INSERT event into outbox.

        Args:
            event: The integration event to enqueue.
            conn: Optional existing connection (for transactional use).
                  If None, creates a new connection.
        """
        own_conn = False
        if conn is None:
            conn = self._connect()
            own_conn = True

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO event_outbox (
                        id, event_type, aggregate_type, aggregate_id,
                        payload, metadata, status
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, 'pending'
                    )
                    """,
                    (
                        str(event.event_id),
                        event.event_type,
                        event.aggregate_type,
                        event.aggregate_id,
                        json.dumps(event.to_dict(), default=str),
                        json.dumps(event.metadata or {}, default=str),
                    ),
                )
            if own_conn:
                conn.commit()
            logger.debug(
                "outbox_enqueued",
                event_id=str(event.event_id),
                event_type=event.event_type,
            )
        except Exception:
            if own_conn:
                conn.rollback()
            raise
        finally:
            if own_conn:
                conn.close()

    def fetch_pending(self, limit: int = 50) -> list[dict[str, Any]]:
        """SELECT pending events for publisher.

        Uses FOR UPDATE SKIP LOCKED to support concurrent publishers.
        """
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_type, aggregate_type, aggregate_id,
                           payload, metadata, created_at, published_at,
                           attempts, last_error, status
                    FROM event_outbox
                    WHERE status = 'pending'
                    ORDER BY created_at
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "event_type": r[1],
                    "aggregate_type": r[2],
                    "aggregate_id": r[3],
                    "payload": r[4],
                    "metadata": r[5],
                    "created_at": r[6],
                    "published_at": r[7],
                    "attempts": r[8],
                    "last_error": r[9],
                    "status": r[10],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def mark_published(self, event_id: UUID) -> None:
        """Mark event as published."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE event_outbox
                    SET status = 'published',
                        published_at = NOW()
                    WHERE id = %s
                    """,
                    (event_id,),
                )
            conn.commit()
            logger.debug("outbox_marked_published", event_id=str(event_id))
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def mark_failed(self, event_id: UUID, error: str) -> None:
        """Mark event as failed. Increments attempts, sets last_error.

        After 3 failed attempts → status = 'dead'.
        """
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                # Increment attempts and set last_error
                cur.execute(
                    """
                    UPDATE event_outbox
                    SET attempts = attempts + 1,
                        last_error = %s,
                        status = CASE
                            WHEN attempts + 1 >= 3 THEN 'dead'
                            ELSE 'failed'
                        END
                    WHERE id = %s
                    """,
                    (error, event_id),
                )
            conn.commit()
            logger.warning(
                "outbox_marked_failed",
                event_id=str(event_id),
                error=error,
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fetch_failed(self, max_retries: int = 3, limit: int = 100) -> list[dict[str, Any]]:
        """Select failed events that haven't exceeded max retries."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_type, aggregate_type, aggregate_id,
                           payload, metadata, created_at, published_at,
                           attempts, last_error, status
                    FROM event_outbox
                    WHERE status = 'failed' AND attempts < %s
                    ORDER BY created_at
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (max_retries, limit),
                )
                rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "event_type": r[1],
                    "aggregate_type": r[2],
                    "aggregate_id": r[3],
                    "payload": r[4],
                    "metadata": r[5],
                    "created_at": r[6],
                    "published_at": r[7],
                    "attempts": r[8],
                    "last_error": r[9],
                    "status": r[10],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def retry(self, event_id: UUID) -> None:
        """Reset event to pending for retry (admin API)."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE event_outbox
                    SET status = 'pending',
                        last_error = NULL
                    WHERE id = %s
                    """,
                    (event_id,),
                )
            conn.commit()
            logger.info("outbox_retry", event_id=str(event_id))
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
