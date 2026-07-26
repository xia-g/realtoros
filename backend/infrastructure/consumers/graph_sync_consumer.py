"""GraphSyncConsumer — синхронизирует CRM-сущности с Knowledge Graph.

Получает IntegrationEvent через Publisher, использует dedup по event_id.
Наследует BaseConsumer — встроенная идемпотентность через ConsumerStateRepository.

Backward compatibility: старый graph_sync_handler (DomainEventBus) продолжает
работать параллельно. После подтверждения миграции — удалить.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker
from structlog import get_logger

from backend.core.integration_event import IntegrationEvent
from backend.infrastructure.consumer_base import (
    BaseConsumer,
    ConsumerResult,
)

logger = get_logger(__name__)


class GraphSyncConsumer(BaseConsumer):
    """GraphSync consumer — синхронизирует CRM-сущности с Knowledge Graph.

    Получает IntegrationEvent через Publisher, использует dedup по event_id
    через ConsumerStateRepository (унаследован от BaseConsumer).
    """

    consumer_name = "graph_sync"

    def __init__(self, dsn: str, session_factory: async_sessionmaker):
        super().__init__(consumer_name=self.consumer_name, dsn=dsn)
        self._session_factory = session_factory

    async def _process(self, event: IntegrationEvent) -> None:
        """Process an integration event by syncing the entity to the graph.

        Extracts entity_type and entity_id from the IntegrationEvent envelope
        and delegates to GraphLifecycleService.sync_entity().
        """
        from backend.services.graph_lifecycle_service import GraphLifecycleService

        entity_type = event.aggregate_type
        entity_id = event.aggregate_id
        # Use the event_type prefix as a human-readable title/description
        source_label = event.event_type.split(".")[0]

        try:
            entity_id_uuid = UUID(str(entity_id))
        except (ValueError, AttributeError):
            entity_id_uuid = entity_id

        async with self._session_factory() as session:
            svc = GraphLifecycleService(session=session)
            await svc.sync_entity(
                entity_type=entity_type,
                entity_id=entity_id_uuid,
                title=source_label,
                metadata=event.payload,
            )
            await session.commit()

        logger.info(
            "graph_sync_consumer_completed",
            event_id=str(event.event_id),
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
        )
