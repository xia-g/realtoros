"""
Knowledge Consistency Check — stateless unit tests.

Tests the check_snapshot_consistency function directly.
No database needed.
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
from domain.business_relationship.kg_identifiers import GraphNodeId

from application.capabilities.consistency_check import check_snapshot_consistency


def _node(nid: str, domain_id: str = "", ntype: GraphNodeType = GraphNodeType.ENTITY) -> GraphNode:
    return GraphNode(
        node_id=GraphNodeId(value=nid),
        node_type=ntype,
        domain_id=domain_id or nid,
        attributes=GraphAttributes(label=domain_id or nid),
        metadata=GraphMetadata(created_by="test"),
    )


def _edge(eid: str, src: str, tgt: str, etype: GraphEdgeType = GraphEdgeType.REFERENCES) -> GraphEdge:
    return GraphEdge(
        edge_id=GraphEdgeId(value=eid),
        edge_type=etype,
        source_node=GraphNodeId(value=src),
        target_node=GraphNodeId(value=tgt),
        attributes=GraphAttributes(),
        metadata=GraphMetadata(created_by="test"),
    )


def _link(gid: str) -> ProvenanceLink:
    return ProvenanceLink(
        graph_node_id=GraphNodeId(value=gid),
        source=ProvenanceSource(
            source_type=ProvenanceSourceType.DOCUMENT,
            source_id="doc-001",
        ),
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


class TestConsistencyCheck:

    def test_valid_snapshot_passes(self):
        """Well-formed snapshot with edges and provenance → no violations."""
        a = _node("n1", "ent-a")
        b = _node("n2", "ent-b")
        snap = _snapshot(
            nodes=(a, b),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"), _link("n2")),
        )
        result = check_snapshot_consistency(snap)
        assert result.is_consistent
        assert len(result.violations) == 0

    def test_broken_edge_detected(self):
        """Edge referencing non-existent node_id → error."""
        a = _node("n1", "ent-a")
        snap = _snapshot(
            nodes=(a,),
            edges=(_edge("e1", "n1", "missing-node"),),
        )
        result = check_snapshot_consistency(snap)
        assert not result.is_consistent
        assert any(v.violation_type == "broken_edge" for v in result.violations)

    def test_orphan_node_detected(self):
        """Node with no edges → warning."""
        a = _node("n1", "ent-a")
        snap = _snapshot(nodes=(a,))
        result = check_snapshot_consistency(snap)
        assert not result.is_consistent
        assert any(v.violation_type == "orphan_node" for v in result.violations)

    def test_duplicate_node_detected(self):
        """Same (node_type, domain_id) appears twice → error."""
        a = _node("n1", "ent-dup")
        b = _node("n2", "ent-dup")
        snap = _snapshot(nodes=(a, b), edges=(_edge("e1", "n1", "n2"),))
        result = check_snapshot_consistency(snap)
        assert not result.is_consistent
        assert any(v.violation_type == "duplicate_node" for v in result.violations)

    def test_self_reference_detected(self):
        """Edge where source == target → warning."""
        a = _node("n1", "ent-a")
        snap = _snapshot(
            nodes=(a,),
            edges=(_edge("e1", "n1", "n1"),),
            links=(_link("n1"),),
        )
        result = check_snapshot_consistency(snap)
        assert not result.is_consistent
        assert any(v.violation_type == "self_reference" for v in result.violations)

    def test_missing_provenance_detected(self):
        """Node with no provenance link → warning."""
        a = _node("n1", "ent-a")
        b = _node("n2", "ent-b")
        snap = _snapshot(
            nodes=(a, b),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"),),  # n2 has no provenance
        )
        result = check_snapshot_consistency(snap)
        assert not result.is_consistent
        assert any(v.violation_type == "missing_provenance" for v in result.violations)

    def test_empty_graph_no_errors(self):
        """Empty graph → no violations (not an error)."""
        snap = _snapshot()
        result = check_snapshot_consistency(snap)
        assert result.is_consistent
        assert len(result.violations) == 0

    def test_multiple_violations_stable_ordering(self):
        """Violations sorted by severity → type → domain_id deterministically."""
        a = _node("n1", "ent-a")
        b = _node("n2", "ent-b")
        c = _node("n3", "ent-c")
        snap = _snapshot(
            nodes=(a, b, c),  # all orphan
            edges=(_edge("e1", "n1", "missing-x"),),
        )
        r1 = check_snapshot_consistency(snap)
        r2 = check_snapshot_consistency(snap)
        # Same violation list, same order
        assert len(r1.violations) == len(r2.violations)
        for v1, v2 in zip(r1.violations, r2.violations):
            assert v1.violation_type == v2.violation_type
            assert v1.affected_domain_id == v2.affected_domain_id

    def test_deterministic(self):
        """Same input → same output."""
        a = _node("n1", "ent-a")
        b = _node("n2", "ent-b")
        snap = _snapshot(
            nodes=(a, b),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"), _link("n2")),
        )
        r1 = check_snapshot_consistency(snap)
        r2 = check_snapshot_consistency(snap)
        assert r1.is_consistent == r2.is_consistent
        assert len(r1.violations) == len(r2.violations)

    def test_invalid_relation_empty_type(self):
        """Edge with empty edge_type → error."""
        a = _node("n1")
        b = _node("n2")
        snap = _snapshot(
            nodes=(a, b),
            edges=(GraphEdge(
                edge_id=GraphEdgeId(value="e1"),
                edge_type="",
                source_node=GraphNodeId(value="n1"),
                target_node=GraphNodeId(value="n2"),
            ),),
            links=(_link("n1"), _link("n2")),
        )
        result = check_snapshot_consistency(snap)
        assert any(v.violation_type == "invalid_relation" for v in result.violations)
