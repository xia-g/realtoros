"""Domain Event Bus — синхронная шина событий уровня домена.

Events:
- ClientCreated/Updated/Deleted
- PropertyCreated/Updated/Deleted
- DealCreated/Updated/Deleted
- DocumentCreated/Deleted
- LeadConverted/LeadMerged
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class DomainEvent:
    """Базовый доменный event."""
    event_type: str
    entity_type: str
    entity_id: UUID
    actor_id: str = "system"
    correlation_id: str = ""
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


EventHandler = Callable[[DomainEvent], Any]


class DomainEventBus:
    """Синхронная шина событий.

    Handler'ы вызываются последовательно в порядке регистрации.
    """

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = {}

    def register(self, event_type: str, handler: EventHandler) -> None:
        """Зарегистрировать handler на тип события."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info("event_handler_registered", event_type=event_type, handler=handler.__name__)

    async def emit(self, event: DomainEvent) -> None:
        """Эмитировать событие — вызвать все handler'ы."""
        handlers = self._handlers.get(event.event_type, [])
        logger.info("event_emitted", event_type=event.event_type, entity_id=str(event.entity_id), handlers=len(handlers))
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error("event_handler_failed", event_type=event.event_type, handler=handler.__name__, error=str(e))

    def register_all(self, handlers: dict[str, list[EventHandler]]) -> None:
        """Зарегистрировать группу handler'ов."""
        for event_type, handler_list in handlers.items():
            for handler in handler_list:
                self.register(event_type, handler)


# ─── Built-in Event Types ───

EVENT_CLIENT_CREATED = "client.created"
EVENT_CLIENT_UPDATED = "client.updated"
EVENT_CLIENT_DELETED = "client.deleted"

EVENT_PROPERTY_CREATED = "property.created"
EVENT_PROPERTY_UPDATED = "property.updated"
EVENT_PROPERTY_DELETED = "property.deleted"

EVENT_DEAL_CREATED = "deal.created"
EVENT_DEAL_UPDATED = "deal.updated"
EVENT_DEAL_DELETED = "deal.deleted"

EVENT_DOCUMENT_CREATED = "document.created"
EVENT_DOCUMENT_DELETED = "document.deleted"

EVENT_LEAD_CONVERTED = "lead.converted"
EVENT_LEAD_MERGED = "lead.merged"


# ─── Singleton ───

_bus: DomainEventBus | None = None


def get_event_bus() -> DomainEventBus:
    """Получить глобальный event bus (singleton)."""
    global _bus
    if _bus is None:
        _bus = DomainEventBus()
    return _bus
