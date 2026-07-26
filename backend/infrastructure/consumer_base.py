"""Consumer Framework — base classes for event consumers.

Each consumer:
1. Checks dedup (consumer_processed_events) -> skip if already processed
2. Processes the event
3. Marks processed on success
4. On failure -> does NOT mark processed -> retry will pick it up
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from structlog import get_logger

from backend.core.integration_event import IntegrationEvent
from backend.repositories.consumer_state_repository import ConsumerStateRepository

logger = get_logger(__name__)


@dataclass(frozen=True)
class ConsumerResult:
    """Result of processing an event.

    Attributes:
        success: True if processing succeeded.
        error: Error message if failed.
        retryable: If False -> poison message -> dead letter.
    """

    success: bool
    error: str | None = None
    retryable: bool = True


class EventConsumer(Protocol):
    """Contract for event consumers.

    Each consumer MUST be idempotent.
    """

    async def consume(self, event: IntegrationEvent) -> ConsumerResult:
        """Process an integration event. Return success/failure."""
        ...


class BaseConsumer(ABC):
    """Base class for idempotent event consumers.

    Provides built-in dedup via ConsumerStateRepository.
    Subclasses implement _process() for actual business logic.
    """

    def __init__(self, consumer_name: str, dsn: str):
        self._consumer_name = consumer_name
        self._state_repo = ConsumerStateRepository(dsn)

    async def consume(self, event: IntegrationEvent) -> ConsumerResult:
        """Consume an event with idempotency guard.

        1. Check if already processed -> skip
        2. Process the event
        3. Mark processed on success
        4. On error -> don't mark processed -> retry picks it up
        """
        # 1. Dedup check
        if self._state_repo.is_processed(self._consumer_name, event.event_id):
            logger.debug(
                "consumer_duplicate_skipped",
                consumer=self._consumer_name,
                event_id=str(event.event_id),
                event_type=event.event_type,
            )
            return ConsumerResult(success=True)

        # 2. Process
        try:
            await self._process(event)
            # 3. Mark processed
            self._state_repo.mark_processed(self._consumer_name, event.event_id)
            logger.info(
                "consumer_processed",
                consumer=self._consumer_name,
                event_id=str(event.event_id),
                event_type=event.event_type,
            )
            return ConsumerResult(success=True)
        except Exception as e:
            logger.error(
                "consumer_failed",
                consumer=self._consumer_name,
                event_id=str(event.event_id),
                event_type=event.event_type,
                error=str(e),
            )
            # 4. Error -> don't mark processed -> retry will pick it up
            return ConsumerResult(success=False, error=str(e), retryable=True)

    @abstractmethod
    async def _process(self, event: IntegrationEvent) -> None:
        """Actual business logic for processing the event.

        Subclasses implement this.
        If it raises, the event will be retried.
        """
        ...
