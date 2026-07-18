"""
GraphEdgeFactory — creates individual GraphEdge instances.

Stateless. Deterministic. NO knowledge of the full graph.
"""
from __future__ import annotations

from domain.business_relationship.kg_identifiers import GraphEdgeId, GraphNodeId
from domain.business_relationship.kg_enums import GraphEdgeType
from domain.business_relationship.kg_edge import GraphEdge


class GraphEdgeFactory:
    """Создаёт рёбра графа. Не знает о KnowledgeGraph."""

    @staticmethod
    def create_has_fact(source: GraphNodeId, target: GraphNodeId) -> GraphEdge:
        return GraphEdge(
            edge_id=GraphEdgeId.generate(),
            edge_type=GraphEdgeType.HAS_FACT,
            source_node=source,
            target_node=target,
        )

    @staticmethod
    def create_has_agreement(source: GraphNodeId, target: GraphNodeId) -> GraphEdge:
        return GraphEdge(
            edge_id=GraphEdgeId.generate(),
            edge_type=GraphEdgeType.HAS_AGREEMENT,
            source_node=source,
            target_node=target,
        )

    @staticmethod
    def create_owns(source: GraphNodeId, target: GraphNodeId) -> GraphEdge:
        return GraphEdge(
            edge_id=GraphEdgeId.generate(),
            edge_type=GraphEdgeType.OWNS,
            source_node=source,
            target_node=target,
        )

    @staticmethod
    def create_participates(source: GraphNodeId, target: GraphNodeId) -> GraphEdge:
        return GraphEdge(
            edge_id=GraphEdgeId.generate(),
            edge_type=GraphEdgeType.PARTICIPATES,
            source_node=source,
            target_node=target,
        )

    @staticmethod
    def create_references(source: GraphNodeId, target: GraphNodeId) -> GraphEdge:
        return GraphEdge(
            edge_id=GraphEdgeId.generate(),
            edge_type=GraphEdgeType.REFERENCES,
            source_node=source,
            target_node=target,
        )

    @staticmethod
    def create_related_to(source: GraphNodeId, target: GraphNodeId) -> GraphEdge:
        return GraphEdge(
            edge_id=GraphEdgeId.generate(),
            edge_type=GraphEdgeType.RELATED_TO,
            source_node=source,
            target_node=target,
        )
