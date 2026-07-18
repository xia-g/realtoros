"""
GraphNode — immutable node in the Knowledge Graph.

Pure data. NO methods for traversal, mutation, or validation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_enums import GraphNodeType
from domain.business_relationship.kg_attributes import GraphAttributes, GraphMetadata


@dataclass(frozen=True)
class GraphNode:
    """Узел графа знаний. Immutable. Без логики."""
    node_id: GraphNodeId
    node_type: GraphNodeType
    domain_id: str
    attributes: GraphAttributes = field(default_factory=GraphAttributes)
    metadata: GraphMetadata = field(default_factory=GraphMetadata)
