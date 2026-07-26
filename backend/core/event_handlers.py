"""Event sync handlers — синхронизация CRM -> Embeddings / Search / Audit.

Подключаются к DomainEventBus.
Версия 4: Legacy graph_sync_handler removed — migrated to Event Backbone.
"""
from __future__ import annotations

from structlog import get_logger

from backend.core.domain_events import DomainEvent

logger = get_logger(__name__)


async def embedding_sync_handler(event: DomainEvent) -> None:
    """Перестроить embedding при изменении документа."""
    logger.info(
        "embedding_sync",
        event_type=event.event_type,
        entity_id=str(event.entity_id),
    )


async def search_index_handler(event: DomainEvent) -> None:
    """Обновить поисковый индекс."""
    logger.info(
        "search_index_sync",
        event_type=event.event_type,
        entity_id=str(event.entity_id),
    )


async def audit_handler(event: DomainEvent) -> None:
    """Записать событие в audit log."""
    logger.info(
        "domain_audit",
        event_type=event.event_type,
        entity_id=str(event.entity_id),
        payload=event.payload,
        actor_id=event.actor_id,
    )


def register_sync_handlers(event_bus) -> None:
    """Зарегистрировать все sync handler'ы на event bus."""
    from backend.core.domain_events import (
        EVENT_CLIENT_CREATED,
        EVENT_CLIENT_UPDATED,
        EVENT_CLIENT_DELETED,
        EVENT_PROPERTY_CREATED,
        EVENT_PROPERTY_UPDATED,
        EVENT_PROPERTY_DELETED,
        EVENT_DEAL_CREATED,
        EVENT_DEAL_UPDATED,
        EVENT_DEAL_DELETED,
        EVENT_DOCUMENT_CREATED,
        EVENT_DOCUMENT_DELETED,
        EVENT_LEAD_CONVERTED,
        EVENT_LEAD_MERGED,
    )

    handlers = {
        EVENT_CLIENT_CREATED: [audit_handler],
        EVENT_CLIENT_UPDATED: [audit_handler],
        EVENT_CLIENT_DELETED: [audit_handler],
        EVENT_PROPERTY_CREATED: [audit_handler],
        EVENT_PROPERTY_UPDATED: [audit_handler],
        EVENT_PROPERTY_DELETED: [audit_handler],
        EVENT_DEAL_CREATED: [audit_handler],
        EVENT_DEAL_UPDATED: [audit_handler],
        EVENT_DEAL_DELETED: [audit_handler],
        EVENT_DOCUMENT_CREATED: [
            embedding_sync_handler,
            search_index_handler,
            audit_handler,
        ],
        EVENT_DOCUMENT_DELETED: [
            embedding_sync_handler,
            search_index_handler,
            audit_handler,
        ],
        EVENT_LEAD_CONVERTED: [audit_handler],
        EVENT_LEAD_MERGED: [audit_handler],
    }

    event_bus.register_all(handlers)
    logger.info(
        "sync_handlers_registered",
        count=sum(len(v) for v in handlers.values()),
    )
