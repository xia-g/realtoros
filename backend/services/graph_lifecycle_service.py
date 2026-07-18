"""GraphLifecycleService — управление жизненным циклом графовых узлов."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update

from backend.models.graph_node import GraphNode
from backend.models.graph_edge import GraphEdge
from backend.core.domain_events import DomainEvent, get_event_bus

from structlog import get_logger

logger = get_logger(__name__)


class GraphLifecycleService:
    """Сервис для создания, удаления, восстановления и синхронизации узлов графа."""

    def __init__(self, session):
        self.session = session

    async def create_node(
        self,
        node_type: str,
        entity_id: UUID,
        title: str,
        source_entity_type: str = "",
        source_entity_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> GraphNode:
        """Создать узел графа с source_entity tracking."""
        node = GraphNode(
            node_type=node_type,
            entity_id=entity_id,
            source_entity_type=source_entity_type or node_type,
            source_entity_id=source_entity_id or entity_id,
            title=title,
            metadata=metadata,
        )
        self.session.add(node)
        await self.session.flush()
        logger.info("graph_node_created", node_id=str(node.id), entity_type=node_type, entity_id=str(entity_id))
        return node

    async def soft_delete_node(self, node_id: UUID) -> bool:
        """Мягкое удаление узла."""
        result = await self.session.execute(
            update(GraphNode)
            .where(GraphNode.id == node_id, GraphNode.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc))
        )
        affected = result.rowcount
        if affected:
            # Also soft-delete edges
            await self.session.execute(
                update(GraphEdge)
                .where(
                    (GraphEdge.source_node_id == node_id) | (GraphEdge.target_node_id == node_id),
                    GraphEdge.deleted_at.is_(None),
                )
                .values(deleted_at=datetime.now(timezone.utc))
            )
            logger.info("graph_node_soft_deleted", node_id=str(node_id))
        return affected > 0

    async def restore_node(self, node_id: UUID) -> bool:
        """Восстановить мягко удалённый узел."""
        result = await self.session.execute(
            update(GraphNode)
            .where(GraphNode.id == node_id, GraphNode.deleted_at.is_not(None))
            .values(deleted_at=None)
        )
        return result.rowcount > 0

    async def sync_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        title: str,
        metadata: dict | None = None,
    ) -> GraphNode | None:
        """Синхронизировать CRM-сущность с графом: создать или обновить."""
        result = await self.session.execute(
            select(GraphNode).where(
                GraphNode.source_entity_type == entity_type,
                GraphNode.source_entity_id == entity_id,
                GraphNode.deleted_at.is_(None),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.title = title
            existing.metadata = metadata or existing.metadata
            await self.session.flush()
            logger.info("graph_node_synced", node_id=str(existing.id), entity_type=entity_type)
            return existing

        return await self.create_node(
            node_type=entity_type,
            entity_id=entity_id,
            title=title,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            metadata=metadata,
        )
