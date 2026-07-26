"""EventRepository — append-only event log operations.

Append business events, replay for consumers.
Only INSERT — never UPDATE/DELETE (append-only invariant).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from structlog import get_logger

from backend.core.integration_event import IntegrationEvent

logger = get_logger(__name__)


class EventRepository:
    """Repository for business_events table (append-only event log)."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self._dsn)

    def append(self, event: IntegrationEvent, conn=None) -> None:
        """INSERT event into business_events (append-only)."""
        own_conn = False
        if conn is None:
            conn = self._connect()
            own_conn = True

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO business_events (
                        event_id, event_type, aggregate_type, aggregate_id,
                        occurred_at, version, payload, metadata
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s::jsonb, %s::jsonb
                    )
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (
                        event.event_id,
                        event.event_type,
                        event.aggregate_type,
                        event.aggregate_id,
                        event.occurred_at,
                        event.version,
                        json.dumps(event.payload, default=str),
                        json.dumps(event.metadata or {}, default=str),
                    ),
                )
            if own_conn:
                conn.commit()
            logger.debug("event_appended", event_id=str(event.event_id))
        except Exception:
            if own_conn:
                conn.rollback()
            raise
        finally:
            if own_conn:
                conn.close()

    def replay_by_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[IntegrationEvent]:
        """Replay events for a specific aggregate, ordered by occurred_at."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id, event_type, aggregate_type, aggregate_id,
                           occurred_at, version, payload, metadata
                    FROM business_events
                    WHERE aggregate_type = %s AND aggregate_id = %s
                    ORDER BY occurred_at
                    LIMIT %s OFFSET %s
                    """,
                    (aggregate_type, aggregate_id, limit, offset),
                )
                return [self._row_to_event(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def replay_by_type(
        self,
        event_type: str,
        from_timestamp: datetime | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[IntegrationEvent]:
        """Replay events by type, optionally from a timestamp."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                if from_timestamp:
                    cur.execute(
                        """
                        SELECT event_id, event_type, aggregate_type, aggregate_id,
                               occurred_at, version, payload, metadata
                        FROM business_events
                        WHERE event_type = %s AND occurred_at >= %s
                        ORDER BY occurred_at
                        LIMIT %s OFFSET %s
                        """,
                        (event_type, from_timestamp, limit, offset),
                    )
                else:
                    cur.execute(
                        """
                        SELECT event_id, event_type, aggregate_type, aggregate_id,
                               occurred_at, version, payload, metadata
                        FROM business_events
                        WHERE event_type = %s
                        ORDER BY occurred_at
                        LIMIT %s OFFSET %s
                        """,
                        (event_type, limit, offset),
                    )
                return [self._row_to_event(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def replay_all(self, from_sequence: int = 0, limit: int = 1000) -> list[IntegrationEvent]:
        """Replay all events, ordered by occurred_at + event_id."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id, event_type, aggregate_type, aggregate_id,
                           occurred_at, version, payload, metadata
                    FROM business_events
                    ORDER BY occurred_at, event_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, from_sequence),
                )
                return [self._row_to_event(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_event(self, event_id: UUID) -> IntegrationEvent | None:
        """Get a single event by ID."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id, event_type, aggregate_type, aggregate_id,
                           occurred_at, version, payload, metadata
                    FROM business_events
                    WHERE event_id = %s
                    """,
                    (event_id,),
                )
                row = cur.fetchone()
                return self._row_to_event(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _row_to_event(row: tuple) -> IntegrationEvent:
        """Convert a DB row to an IntegrationEvent."""
        return IntegrationEvent(
            event_id=row[0],
            event_type=row[1],
            aggregate_type=row[2],
            aggregate_id=row[3],
            occurred_at=row[4],
            version=row[5],
            payload=row[6] if isinstance(row[6], dict) else {},
            metadata=row[7] if isinstance(row[7], dict) else {},
        )
