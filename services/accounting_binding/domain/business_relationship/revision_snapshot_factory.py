"""
RevisionSnapshotFactory — creates KnowledgeSnapshot from domain objects.

Stateless. NO revision knowledge. NO builder knowledge.
"""
from __future__ import annotations

from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.ke_explanation import GraphExplanation


class RevisionSnapshotFactory:
    """Создаёт Snapshot. Не знает Revision. Не знает Builder."""

    @staticmethod
    def empty() -> KnowledgeSnapshot:
        """Create empty snapshot."""
        return KnowledgeSnapshot.empty()

    @staticmethod
    def from_graph(graph: KnowledgeGraph) -> KnowledgeSnapshot:
        """Create snapshot from graph only."""
        return KnowledgeSnapshot(graph=graph)

    @staticmethod
    def from_provenance(provenance: KnowledgeProvenance) -> KnowledgeSnapshot:
        """Create snapshot from provenance only."""
        return KnowledgeSnapshot(graph=KnowledgeGraph(), provenance=provenance)

    @staticmethod
    def from_explanation(explanation: GraphExplanation) -> KnowledgeSnapshot:
        """Create snapshot from explanation only."""
        return KnowledgeSnapshot(graph=KnowledgeGraph(), explanation=explanation)

    @staticmethod
    def create(
        graph: KnowledgeGraph,
        provenance: KnowledgeProvenance | None = None,
        explanation: GraphExplanation | None = None,
    ) -> KnowledgeSnapshot:
        """Create snapshot from all available data."""
        return KnowledgeSnapshot(graph=graph, provenance=provenance, explanation=explanation)
