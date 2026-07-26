"""
Knowledge Trust State — stateless unit tests.

Tests evaluate_trust() directly. No database needed.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")

from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_edge import GraphEdge
from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType
from domain.business_relationship.kg_identifiers import GraphNodeId, GraphEdgeId
from domain.business_relationship.kg_attributes import GraphAttributes, GraphMetadata
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.kg_provenance_chain import ProvenanceChain
from domain.business_relationship.kg_provenance_link import ProvenanceLink
from domain.business_relationship.kg_provenance_source import ProvenanceSource, ProvenanceSourceType
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.ke_explanation_step import ExplanationStep
from domain.business_relationship.kg_identifiers import GraphNodeId

from application.capabilities.trust_state import evaluate_trust


def _node(nid: str, did: str = "") -> GraphNode:
    return GraphNode(
        node_id=GraphNodeId(value=nid),
        node_type=GraphNodeType.ENTITY,
        domain_id=did or nid,
        attributes=GraphAttributes(label=did or nid),
        metadata=GraphMetadata(created_by="test"),
    )


def _edge(eid: str, src: str, tgt: str, etype: GraphEdgeType = GraphEdgeType.REFERENCES) -> GraphEdge:
    return GraphEdge(
        edge_id=GraphEdgeId(value=eid),
        edge_type=etype,
        source_node=GraphNodeId(value=src),
        target_node=GraphNodeId(value=tgt),
    )


def _link(gid: str) -> ProvenanceLink:
    return ProvenanceLink(
        graph_node_id=GraphNodeId(value=gid),
        source=ProvenanceSource(source_type=ProvenanceSourceType.DOCUMENT, source_id="doc"),
    )


def _snapshot(nodes: tuple = (), edges: tuple = (), links: tuple = ()) -> KnowledgeSnapshot:
    return KnowledgeSnapshot(
        graph=KnowledgeGraph(nodes=nodes, edges=edges),
        provenance=KnowledgeProvenance(
            provenance_id=ProvenanceId.generate(),
            chain=ProvenanceChain(links=links),
        ),
        explanation=GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="root"),
        ),
    )


class TestTrustState:

    def test_valid_snapshot(self):
        """Well-formed snapshot → VALID."""
        a = _node("n1", "ent-a")
        b = _node("n2", "ent-b")
        snap = _snapshot(
            nodes=(a, b),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"), _link("n2")),
        )
        result = evaluate_trust(snap)
        assert result.trust.status == "VALID"

    def test_broken_edge(self):
        """Broken edge → INVALID."""
        a = _node("n1", "ent-a")
        snap = _snapshot(
            nodes=(a,),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        result = evaluate_trust(snap)
        assert result.trust.status == "INVALID"

    def test_orphan_node(self):
        """Orphan node → WARNING."""
        a = _node("n1", "ent-a")
        b = _node("n2", "ent-b")
        snap = _snapshot(
            nodes=(a, b),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"),),  # n2 has no link
        )
        result = evaluate_trust(snap)
        assert result.trust.status == "WARNING"

    def test_empty_snapshot(self):
        """Empty graph → UNKNOWN."""
        snap = KnowledgeSnapshot(
            graph=KnowledgeGraph(),
            provenance=KnowledgeProvenance(provenance_id=ProvenanceId.generate()),
            explanation=GraphExplanation(
                explanation_id=ExplanationId.generate(),
                graph_node_id=GraphNodeId(value="root"),
            ),
        )
        result = evaluate_trust(snap)
        assert result.trust.status == "UNKNOWN"

    def test_structural_errors_count(self):
        """INVALID status has correct structural_errors count."""
        a = _node("n1", "ent-a")
        snap = _snapshot(
            nodes=(a,),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        result = evaluate_trust(snap)
        assert result.trust.structural_errors >= 1

    def test_reasons_present(self):
        """Invalid/WARNING/INVALID have reasons."""
        a = _node("n1", "ent-a")
        snap = _snapshot(
            nodes=(a,),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        result = evaluate_trust(snap)
        assert len(result.trust.reasons) > 0

    def test_deterministic(self):
        """Same snapshot → same trust."""
        a = _node("n1", "ent-a")
        b = _node("n2", "ent-b")
        snap = _snapshot(
            nodes=(a, b),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"), _link("n2")),
        )
        r1 = evaluate_trust(snap)
        r2 = evaluate_trust(snap)
        assert r1.trust.status == r2.trust.status
        assert r1.trust.reasons == r2.trust.reasons

    def test_provenance_coverage(self):
        """Coverage computed correctly."""
        a = _node("n1", "ent-a")
        b = _node("n2", "ent-b")
        snap = _snapshot(
            nodes=(a, b),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"),),  # only n1 has provenance
        )
        result = evaluate_trust(snap)
        assert result.trust.provenance_coverage == 0.5

    def test_has_provenance_and_explanation(self):
        """Flags correctly set."""
        a = _node("n1", "ent-a")
        snap = _snapshot(nodes=(a,), links=(_link("n1"),))
        result = evaluate_trust(snap)
        assert result.has_provenance is True
        # Empty explanation steps → has_explanation = False
        assert result.has_explanation is False
