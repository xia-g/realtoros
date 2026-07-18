"""
KnowledgeSnapshot — immutable snapshot of knowledge state.

References KnowledgeGraph, Provenance, Explanation.
Pure data. NO methods.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.kg_identifiers import GraphNodeId


@dataclass(frozen=True)
class KnowledgeSnapshot:
    """Снимок состояния знаний. Immutable."""
    graph: KnowledgeGraph
    provenance: KnowledgeProvenance | None = None
    explanation: GraphExplanation | None = None

    @classmethod
    def empty(cls) -> KnowledgeSnapshot:
        """Создаёт пустой снимок."""
        return cls(
            graph=KnowledgeGraph(),
            provenance=KnowledgeProvenance(provenance_id=ProvenanceId.generate()),
            explanation=GraphExplanation(
                explanation_id=ExplanationId.generate(),
                graph_node_id=GraphNodeId(value="root"),
            ),
        )

    @property
    def total_nodes(self) -> int:
        return self.graph.node_count

    @property
    def total_edges(self) -> int:
        return self.graph.edge_count
