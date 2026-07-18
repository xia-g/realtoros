"""
GraphEdge — immutable edge in the Knowledge Graph.

Pure data. NO methods for traversal, mutation, or validation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.kg_identifiers import GraphEdgeId, GraphNodeId
from domain.business_relationship.kg_enums import GraphEdgeType
from domain.business_relationship.kg_attributes import GraphAttributes, GraphMetadata


@dataclass(frozen=True)
class GraphEdge:
    """Ребро графа знаний. Immutable. Без логики."""
    edge_id: GraphEdgeId
    edge_type: GraphEdgeType
    source_node: GraphNodeId
    target_node: GraphNodeId
    attributes: GraphAttributes = field(default_factory=GraphAttributes)
    metadata: GraphMetadata = field(default_factory=GraphMetadata)
