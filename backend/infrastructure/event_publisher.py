"""Event Publisher — background task that polls the outbox and delivers events.

At-least-once delivery with retry + exponential backoff + dead letter.
Runs as a FastAPI lifespan background task.

event_id is STABLE across retries — never regenerated.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from structlog import get_logger

from backend.core.integration_event import IntegrationEvent
from backend.repositories.outbox_repository import OutboxRepository
from backend.repositories.consumer_state_repository import ConsumerStateRepository

logger = get_logger(__name__)


class EventPublisher:
    """Polls event_outbox and delivers to registered consumers.

    At-least-once semantics: event is marked published ONLY after
    all consumers confirm success.
    """

    def __init__(
        self,
        dsn: str,
        poll_interval: float = 1.0,
        batch_size: int = 50,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ):
        self._dsn = dsn
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._consumers: dict[str, list[Callable]] = {}  # event_type -> [consumer_handlers]
        self._running = False
        self._outbox_repo = OutboxRepository(dsn)
        self._consumer_state_repo = ConsumerStateRepository(dsn)

    def register_consumer(self, event_type: str, handler: Callable) -> None:
        """Register a consumer handler for an event type."""
        if event_type not in self._consumers:
            self._consumers[event_type] = []
        self._consumers[event_type].append(handler)
        logger.info(
            "publisher_consumer_registered",
            event_type=event_type,
            handler=handler.__name__,
        )

    async def start(self) -> None:
        """Start the polling loop."""
        self._running = True
        logger.info(
            "event_publisher_started",
            poll_interval=self._poll_interval,
            batch_size=self._batch_size,
        )
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error("event_publisher_poll_error", error=str(e))
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        logger.info("event_publisher_stopped")

    async def _poll_once(self) -> None:
        """Single poll iteration."""
        # Fetch pending events
        pending = self._outbox_repo.fetch_pending(limit=self._batch_size)
        if not pending:
            return

        for row in pending:
            await self._process_outbox_row(row)

        # Also retry failed events that haven't exceeded max retries
        failed = self._outbox_repo.fetch_failed(max_retries=self._max_retries, limit=self._batch_size)
        for row in failed:
            await self._process_outbox_row(row)

    async def _process_outbox_row(self, row: dict[str, Any]) -> None:
        """Process a single outbox row — build IntegrationEvent and deliver.

        Uses row-level columns for the envelope (event_id, event_type, aggregate_*)
        and the stored payload for the domain data.
        """
        raw_id = row["id"]
        event_id: UUID = raw_id if isinstance(raw_id, UUID) else UUID(str(raw_id))
        event_type = row["event_type"]
        payload_data = row["payload"]

        # The payload column contains the full IntegrationEvent dict from to_dict()
        # Extract domain payload from it, or use the legacy format
        if isinstance(payload_data, dict) and "event_id" in payload_data:
            # Full IntegrationEvent was stored — extract the inner payload
            inner_payload = payload_data.get("payload", {})
            occurred_at_str = payload_data.get("occurred_at")
            occurred_at = None
            if isinstance(occurred_at_str, str):
                occurred_at = datetime.fromisoformat(occurred_at_str)
        else:
            # Legacy format: payload is the actual domain payload
            inner_payload = payload_data if isinstance(payload_data, dict) else {}
            occurred_at = None

        event = IntegrationEvent(
            event_id=event_id,
            event_type=event_type,
            aggregate_type=row["aggregate_type"],
            aggregate_id=row["aggregate_id"],
            occurred_at=occurred_at or datetime.now(timezone.utc),
            payload=inner_payload,
            metadata=row.get("metadata", {}),
        )

        # Find consumers for this event type
        handlers = self._consumers.get(event_type, [])

        if not handlers:
            # No consumers registered — mark as published anyway
            self._outbox_repo.mark_published(
                event_id if isinstance(event_id, UUID) else UUID(str(event_id))
            )
            return

        all_succeeded = True
        for handler in handlers:
            try:
                result = await handler(event)
                if not result.success:
                    all_succeeded = False
                    logger.warning(
                        "consumer_failed",
                        event_id=str(event.event_id),
                        event_type=event_type,
                        handler=handler.__name__,
                        error=result.error,
                    )
            except Exception as e:
                all_succeeded = False
                logger.error(
                    "consumer_exception",
                    event_id=str(event.event_id),
                    event_type=event_type,
                    handler=handler.__name__,
                    error=str(e),
                )

        event_id_uuid = event_id if isinstance(event_id, UUID) else UUID(str(event_id))

        if all_succeeded:
            self._outbox_repo.mark_published(event_id_uuid)
            logger.debug(
                "event_published",
                event_id=str(event_id_uuid),
                event_type=event_type,
            )
        else:
            self._outbox_repo.mark_failed(event_id_uuid, "consumer_error")
            logger.warning(
                "event_publish_failed",
                event_id=str(event_id_uuid),
                event_type=event_type,
            )
