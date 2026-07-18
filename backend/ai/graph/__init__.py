"""Knowledge Graph Builder — builds relationship graph from CRM entities.

Node types: client, property, deal, document, lead, communication, organization
Edge types: owns, participates_in, related_to, generated_from, refers_to, converts_to

Idempotent: re-running does not create duplicates (upsert by type+entity_id).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.core.logging import get_logger
from backend.models.graph_node import GraphNode
from backend.models.graph_edge import GraphEdge

logger = get_logger("knowledge")


class KnowledgeGraphBuilder:
    """Build and maintain the relationship graph."""

    def __init__(self, session):
        self.session = session

    async def build_full(self) -> dict:
        """Rebuild entire graph from scratch."""
        from backend.models.client import Client
        from backend.models.property import Property
        from backend.models.deal import Deal
        from backend.models.lead import Lead
        from backend.models.document import Document

        created_nodes = 0
        created_edges = 0

        # Clients -> nodes
        result = await self.session.execute(select(Client).where(Client.deleted_at.is_(None)))
        for client in result.scalars().all():
            await self._upsert_node("client", client.id, client.full_name)
            created_nodes += 1

            # Properties owned by this client
            for prop in (client.properties or []):
                await self._upsert_node("property", prop.id, prop.title or prop.address)
                await self._upsert_edge(client.id, prop.id, "owns", source_type="client", target_type="property")
                created_nodes += 1
                created_edges += 1

        # Deals -> nodes + edges
        result = await self.session.execute(select(Deal))
        for deal in result.scalars().all():
            await self._upsert_node("deal", deal.id, f"Deal #{deal.id}")
            created_nodes += 1

            if deal.property_id:
                await self._upsert_edge(deal.id, deal.property_id, "relates_to", source_type="deal", target_type="property")
                created_edges += 1

        # Leads -> nodes
        result = await self.session.execute(select(Lead))
        for lead in result.scalars().all():
            await self._upsert_node("lead", lead.id, lead.full_name or f"Lead #{lead.id}")
            created_nodes += 1

        logger.info("graph_built", nodes=created_nodes, edges=created_edges)
        return {"nodes": created_nodes, "edges": created_edges}

    async def _upsert_node(self, node_type: str, entity_id: UUID, title: str) -> GraphNode:
        stmt = pg_insert(GraphNode).values(
            node_type=node_type, entity_id=entity_id, title=title[:255]
        ).on_conflict_do_nothing(
            index_elements=["node_type", "entity_id"]
        )
        await self.session.execute(stmt)
        await self.session.flush()
        result = await self.session.execute(
            select(GraphNode).where(GraphNode.node_type == node_type, GraphNode.entity_id == entity_id)
        )
        return result.scalar_one()

    async def _upsert_edge(self, source_id: UUID, target_id: UUID, edge_type: str,
                        source_type: str | None = None, target_type: str | None = None) -> None:
        """Create a typed edge between two entity nodes.

        Args:
            source_id: entity_id of the source node
            target_id: entity_id of the target node
            edge_type: type of relationship
            source_type: node_type of source (required for disambiguation)
            target_type: node_type of target (required for disambiguation)
        """
        source_where = [GraphNode.entity_id == source_id]
        target_where = [GraphNode.entity_id == target_id]
        if source_type:
            source_where.append(GraphNode.node_type == source_type)
        if target_type:
            target_where.append(GraphNode.node_type == target_type)

        source_node = await self.session.execute(
            select(GraphNode).where(*source_where)
        )
        target_node = await self.session.execute(
            select(GraphNode).where(*target_where)
        )
        s_node = source_node.scalar_one_or_none()
        t_node = target_node.scalar_one_or_none()
        if not s_node or not t_node:
            logger.warning(
                "edge_target_missing",
                source_id=str(source_id),
                target_id=str(target_id),
                edge_type=edge_type,
            )
            return

        stmt = pg_insert(GraphEdge).values(
            source_node_id=s_node.id, target_node_id=t_node.id, edge_type=edge_type
        ).on_conflict_do_nothing(
            index_elements=["source_node_id", "target_node_id", "edge_type"]
        )
        await self.session.execute(stmt)