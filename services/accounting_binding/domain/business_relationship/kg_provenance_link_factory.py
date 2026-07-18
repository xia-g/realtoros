"""
ProvenanceLinkFactory — creates ProvenanceLink instances.

Stateless. NO navigation. NO analysis.
"""
from __future__ import annotations

from domain.business_relationship.kg_provenance_link import ProvenanceLink
from domain.business_relationship.kg_provenance_source import ProvenanceSource, ProvenanceSourceType
from domain.business_relationship.kg_identifiers import GraphNodeId


class ProvenanceLinkFactory:
    """Создаёт связи происхождения. Не знает о навигации или Graph."""

    @staticmethod
    def from_node(
        graph_node_id: GraphNodeId,
        source: ProvenanceSource,
        confidence: float = 1.0,
    ) -> ProvenanceLink:
        """Создаёт связь между GraphNode и источником."""
        return ProvenanceLink(
            graph_node_id=graph_node_id,
            source=source,
            confidence=confidence,
        )

    @staticmethod
    def from_edge(
        edge_id: str,
        source: ProvenanceSource,
        confidence: float = 0.9,
    ) -> ProvenanceLink:
        """Создаёт связь между GraphEdge и источником."""
        return ProvenanceLink(
            graph_node_id=GraphNodeId(value=edge_id),
            source=source,
            confidence=confidence,
        )

    @staticmethod
    def from_source(
        source_id: str,
        source_type: str,
        confidence: float = 1.0,
    ) -> ProvenanceLink:
        """Создаёт связь с источником без GraphNode."""
        return ProvenanceLink(
            graph_node_id=GraphNodeId(value=f"src-{source_id}"),
            source=ProvenanceSource(
                source_type=ProvenanceSourceType(source_type),
                source_id=source_id,
            ),
            confidence=confidence,
        )
