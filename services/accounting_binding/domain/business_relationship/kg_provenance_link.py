"""
ProvenanceLink — immutable link between GraphNode and ProvenanceSource.

Pure data. No navigation. No traversal.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_provenance_source import ProvenanceSource


@dataclass(frozen=True)
class ProvenanceLink:
    """Связь между GraphNode и источником происхождения. Immutable."""
    graph_node_id: GraphNodeId
    source: ProvenanceSource
    confidence: float = 1.0