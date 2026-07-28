"""ConsumerStateRepository — tracks processed events for idempotent consumers.

Each consumer records which event_ids it has processed.
Dedup: if event_id exists for consumer → skip processing.
"""

from __future__ import annotations

from uuid import UUID

from structlog import get_logger

logger = get_logger(__name__)


class ConsumerStateRepository:
    """Repository for consumer_processed_events table."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self._dsn)

    def is_processed(self, consumer_name: str, event_id: UUID) -> bool:
        """Check if an event has been processed by a consumer."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM consumer_processed_events
                    WHERE consumer_name = %s AND event_id = %s
                    """,
                    (consumer_name, str(event_id)),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()

    def mark_processed(self, consumer_name: str, event_id: UUID) -> None:
        """Record that a consumer has processed an event."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO consumer_processed_events (consumer_name, event_id)
                    VALUES (%s, %s)
                    ON CONFLICT (consumer_name, event_id) DO NOTHING
                    """,
                    (consumer_name, str(event_id)),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
