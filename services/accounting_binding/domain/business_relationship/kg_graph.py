"""
KnowledgeGraph — immutable snapshot of the knowledge graph.

Pure data. NO methods for add, connect, traverse, validate, query.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_attributes import GraphMetadata


@dataclass(frozen=True)
class KnowledgeGraph:
    """Граф знаний. Immutable snapshot. Без логики."""
    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()
    metadata: GraphMetadata = field(default_factory=GraphMetadata)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)
