"""
GraphSchema — validation rules for Knowledge Graph edges.

Defines which node types can be connected by which edge types.
Enforced by GraphBuilder before adding any edge.
"""
from __future__ import annotations

from domain.business_relationship.knowledge_graph import GraphNodeType, EdgeType


class GraphValidationError(ValueError):
    """Invalid graph edge — source/target/type combination not allowed."""
    pass


class GraphSchema:
    """Rules for allowed edge connections.

    Edge → (allowed source types, allowed target types)
    """

    RULES: dict[EdgeType, tuple[set[GraphNodeType], set[GraphNodeType]]] = {
        EdgeType.MENTIONS: (
            {GraphNodeType.DOCUMENT},
            {GraphNodeType.ENTITY, GraphNodeType.PROPERTY, GraphNodeType.AGREEMENT, GraphNodeType.DEAL},
        ),
        EdgeType.REFERS_TO: (
            {GraphNodeType.DOCUMENT},
            {GraphNodeType.DOCUMENT},
        ),
        EdgeType.PARTICIPATES_IN: (
            {GraphNodeType.ENTITY},
            {GraphNodeType.AGREEMENT, GraphNodeType.DEAL},
        ),
        EdgeType.SUPPORTS: (
            {GraphNodeType.DOCUMENT, GraphNodeType.AGREEMENT},
            {GraphNodeType.AGREEMENT, GraphNodeType.DEAL},
        ),
        EdgeType.RESULTED_IN: (
            {GraphNodeType.AGREEMENT, GraphNodeType.DOCUMENT},
            {GraphNodeType.DEAL},
        ),
        EdgeType.OWNS: (
            {GraphNodeType.ENTITY},
            {GraphNodeType.PROPERTY},
        ),
        EdgeType.RELATES_TO: (
            {GraphNodeType.ENTITY, GraphNodeType.PROPERTY, GraphNodeType.DOCUMENT,
             GraphNodeType.AGREEMENT, GraphNodeType.DEAL},
            {GraphNodeType.ENTITY, GraphNodeType.PROPERTY, GraphNodeType.DOCUMENT,
             GraphNodeType.AGREEMENT, GraphNodeType.DEAL},
        ),
        EdgeType.ATTACHED_TO: (
            {GraphNodeType.DOCUMENT},
            {GraphNodeType.DEAL, GraphNodeType.AGREEMENT},
        ),
    }

    @classmethod
    def validate(
        cls,
        source_type: GraphNodeType,
        target_type: GraphNodeType,
        edge_type: EdgeType,
        source_id: str = "",
        target_id: str = "",
    ):
        """Validate that edge is allowed. Raises GraphValidationError if invalid."""
        if edge_type not in cls.RULES:
            raise GraphValidationError(f"Unknown edge type: {edge_type.value}")

        allowed_sources, allowed_targets = cls.RULES[edge_type]

        if source_type not in allowed_sources:
            raise GraphValidationError(
                f"Edge {edge_type.value}: source type '{source_type.value}' "
                f"not allowed (allowed: {[t.value for t in allowed_sources]}). "
                f"source={source_id}, target={target_id}"
            )

        if target_type not in allowed_targets:
            raise GraphValidationError(
                f"Edge {edge_type.value}: target type '{target_type.value}' "
                f"not allowed (allowed: {[t.value for t in allowed_targets]}). "
                f"source={source_id}, target={target_id}"
            )

    @classmethod
    def is_valid(
        cls,
        source_type: GraphNodeType,
        target_type: GraphNodeType,
        edge_type: EdgeType,
    ) -> bool:
        """Check if edge type+source+target combination is valid."""
        try:
            cls.validate(source_type, target_type, edge_type)
            return True
        except GraphValidationError:
            return False
