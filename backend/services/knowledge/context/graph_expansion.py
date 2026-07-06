"""Graph expansion — traverses knowledge graph with depth=1, visited set, edge priority.

Cycle protection uses two separate tracking sets:
- visited_entity_ids — for entity UUIDs (ref.entity_id)
- visited_graph_node_ids — for graph_node UUIDs (node.id, edge.source_node_id, edge.target_node_id)

This prevents false dedup between entity_id and graph_node.id which are different
UUID namespaces (H3 fix).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.models.graph_node import GraphNode
from backend.models.graph_edge import GraphEdge
from backend.services.knowledge.context.contracts import (
    MAX_ENTITIES, MAX_GRAPH_DEPTH, MAX_EDGES, Provenance, SOURCES_GRAPH,
)

# Edge priority order (highest first)
EDGE_PRIORITY = {
    "owns": 100,
    "participates_in": 80,
    "related_to": 60,
    "refers_to": 40,
    "mentions": 20,
    "converts_to": 90,
}

# Track coverage of entity_ids vs graph_node_ids separately (H3)
VisitedState = tuple[set[UUID], set[UUID]]


class GraphExpansionService:
    """Expand entities to 1-hop graph neighborhood with cycle protection."""

    def __init__(self, session):
        self.session = session

    async def expand(self, entity_refs: list, max_edges: int = MAX_EDGES) -> tuple[list[dict], list[Provenance]]:
        """Expand entities to 1-hop graph.

        Args:
            entity_refs: list of EntityRef (entity_type, entity_id, score)
            max_edges: maximum edges to return

        Returns:
            (nodes_data: list[dict], provenance: list[Provenance])
        """
        nodes = []
        edges_data = []
        provenance = []

        # H3: separate tracking — entity UUIDs vs graph_node UUIDs
        visited_entity_ids: set[UUID] = set()
        visited_graph_node_ids: set[UUID] = set()

        for ref in entity_refs:
            # Check only entity_ids — not graph_node ids (H3)
            if ref.entity_id in visited_entity_ids:
                continue
            visited_entity_ids.add(ref.entity_id)

            node = await self._get_node(ref.entity_type, ref.entity_id)
            if not node:
                continue

            if node.id in visited_graph_node_ids:
                continue
            visited_graph_node_ids.add(node.id)

            nodes.append({
                "id": str(node.id),
                "entity_type": node.node_type,
                "entity_id": str(node.entity_id),
                "title": node.title,
            })
            provenance.append(Provenance(
                source_type=SOURCES_GRAPH,
                source_id=node.id,
                score=ref.score,
                snippet=node.title[:120],
            ))

            # Get edges (1 hop)
            edges = await self._get_edges(node.id)
            for edge in edges:
                # Determine neighbor graph_node.id
                if edge.source_node_id == node.id:
                    neighbor_id = edge.target_node_id
                else:
                    neighbor_id = edge.source_node_id

                # H3: check graph_node.id — NOT entity_id
                if neighbor_id in visited_graph_node_ids:
                    continue
                visited_graph_node_ids.add(neighbor_id)

                # Get the other node for display
                other = await self._get_node_by_id(neighbor_id)
                if not other:
                    continue

                # Mark entity_id as visited too so entity_ref dedup works (H3)
                visited_entity_ids.add(other.entity_id)

                nodes.append({
                    "id": str(other.id),
                    "entity_type": other.node_type,
                    "entity_id": str(other.entity_id),
                    "title": other.title,
                })

                edges_data.append({
                    "source": str(edge.source_node_id),
                    "target": str(edge.target_node_id),
                    "type": edge.edge_type,
                    "confidence": edge.confidence,
                    "priority": EDGE_PRIORITY.get(edge.edge_type, 0),
                })

        # Sort edges by priority, then confidence
        edges_data.sort(key=lambda e: (-e["priority"], -e["confidence"]))
        edges_data = edges_data[:max_edges]

        return nodes, provenance

    async def _get_node(self, node_type: str, entity_id: UUID) -> GraphNode | None:
        stmt = select(GraphNode).where(
            GraphNode.node_type == node_type,
            GraphNode.entity_id == entity_id,
            GraphNode.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_node_by_id(self, node_id: UUID) -> GraphNode | None:
        stmt = select(GraphNode).where(GraphNode.id == node_id, GraphNode.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_edges(self, node_id: UUID) -> list[GraphEdge]:
        stmt = select(GraphEdge).where(
            (GraphEdge.source_node_id == node_id) | (GraphEdge.target_node_id == node_id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
