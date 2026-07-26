"""Event Publisher — background task that polls the outbox and delivers events.

At-least-once delivery with retry + exponential backoff + dead letter.
Runs as a FastAPI lifespan background task.

event_id is STABLE across retries — never regenerated.

Graceful shutdown:
  - Publisher stops on signal via _stop_event
  - In-flight events are NOT lost: they simply remain in the outbox
    with status='pending'/'failed' and will be picked up on next boot.
"""

from __future__ import annotations

import asyncio
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

    Retry policy:
      - Exponential backoff: 1s → 2s → 4s (configurable via backoff_base)
      - After max_retries failed attempts → status='dead'
      - Dead letter: logged as error, never re-polled

    Graceful shutdown:
      - Set _stop_event → main loop exits after current batch
      - In-flight events stay in outbox (no mark_published → re-picked on restart)
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
        self._in_flight = 0
        self._stop_event = asyncio.Event()
        self._outbox_repo = OutboxRepository(dsn)
        self._consumer_state_repo = ConsumerStateRepository(dsn)

    # ── Public API ──────────────────────────────────────────────────────

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
        """Start the polling loop. Blocks until stop() is called."""
        self._running = True
        self._stop_event.clear()
        logger.info(
            "event_publisher_started",
            poll_interval=self._poll_interval,
            batch_size=self._batch_size,
            max_retries=self._max_retries,
            backoff_base=self._backoff_base,
        )
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error("event_publisher_poll_error", error=str(e))

            # Wait for poll_interval, but allow early exit on shutdown
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._stop_event.wait()),
                    timeout=self._poll_interval,
                )
                # stop_event was set → time to exit
                self._running = False
            except asyncio.TimeoutError:
                # Normal timeout — continue polling
                pass

        # Wait for in-flight events to complete (with timeout)
        if self._in_flight > 0:
            logger.info(
                "event_publisher_draining",
                in_flight=self._in_flight,
            )
            time = 0.0
            while self._in_flight > 0 and time < 10:
                await asyncio.sleep(0.1)
                time += 0.1
            if self._in_flight > 0:
                logger.warning(
                    "event_publisher_drain_timeout",
                    remaining=self._in_flight,
                )
            else:
                logger.info("event_publisher_drained")

        logger.info("event_publisher_stopped")

    async def stop(self) -> None:
        """Initiate graceful shutdown.

        Signals the main loop to exit after the current poll iteration.
        In-flight events are NOT lost — they remain in the outbox
        and will be picked up on the next publisher boot.
        """
        self._running = False
        self._stop_event.set()
        logger.info(
            "event_publisher_stop_requested",
            in_flight=self._in_flight,
        )

    @property
    def in_flight(self) -> int:
        """Number of events currently being processed."""
        return self._in_flight

    # ── Polling ─────────────────────────────────────────────────────────

    async def _poll_once(self) -> None:
        """Single poll iteration: fetch pending + retryable failed events."""
        if self._stop_event.is_set():
            return

        # Fetch pending events
        pending = self._outbox_repo.fetch_pending(limit=self._batch_size)

        for row in pending:
            if self._stop_event.is_set():
                # Graceful shutdown — stop processing new events
                # In-flight event stays in outbox (no mark_published called yet)
                return
            self._in_flight += 1
            try:
                await self._process_outbox_row(row)
            finally:
                self._in_flight -= 1

        # Also retry failed events that haven't exceeded max retries
        failed = self._outbox_repo.fetch_failed(
            max_retries=self._max_retries,
            limit=self._batch_size,
        )
        for row in failed:
            if self._stop_event.is_set():
                return
            self._in_flight += 1
            try:
                # Apply exponential backoff before retrying
                attempts = row.get("attempts", 0)
                backoff_delay = self._backoff_base * (2 ** (attempts - 1))
                if backoff_delay > 0:
                    logger.debug(
                        "event_retry_backoff",
                        event_id=str(row.get("id", "")),
                        event_type=row.get("event_type", ""),
                        attempts=attempts,
                        delay_s=backoff_delay,
                    )
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(self._stop_event.wait()),
                            timeout=backoff_delay,
                        )
                        # stop was requested during backoff
                        return
                    except asyncio.TimeoutError:
                        pass

                await self._process_outbox_row(row)
            finally:
                self._in_flight -= 1

    # ── Event Processing ────────────────────────────────────────────────

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
            self._outbox_repo.mark_published(event_id)
            logger.debug(
                "event_published_no_consumers",
                event_id=str(event_id),
                event_type=event_type,
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
                        retryable=result.retryable,
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

        if all_succeeded:
            self._outbox_repo.mark_published(event_id)
            logger.debug(
                "event_published",
                event_id=str(event_id),
                event_type=event_type,
            )
        else:
            self._outbox_repo.mark_failed(event_id, "consumer_error")
            logger.warning(
                "event_publish_failed",
                event_id=str(event_id),
                event_type=event_type,
            )

            # Dead letter alert: if this failure pushes it over max_retries,
            # log a high-severity alert (actual dead letter state is handled
            # by the SQL CASE in outbox_repository.mark_failed)
            current_attempts = row.get("attempts", 0)
            if current_attempts + 1 >= self._max_retries:
                logger.error(
                    "event_dead_letter",
                    event_id=str(event_id),
                    event_type=event_type,
                    attempts=current_attempts + 1,
                    max_retries=self._max_retries,
                )
