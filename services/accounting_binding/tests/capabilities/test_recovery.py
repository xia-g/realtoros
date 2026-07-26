"""
Knowledge Recovery — unit tests for stateless repair logic.

Tests _repair_snapshot, build_recovery_plan, execute_recovery.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")

from datetime import datetime
from typing import Any
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
from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata

from application.capabilities.recovery import (
    _repair_snapshot,
    build_recovery_plan,
    execute_recovery,
    RepairAction,
)
from application.capabilities.consistency_check import check_snapshot_consistency
from application.capabilities.governance import GovernanceDecision


def _node(nid: str, did: str = "", ntype: GraphNodeType = GraphNodeType.ENTITY) -> GraphNode:
    return GraphNode(
        node_id=GraphNodeId(value=nid),
        node_type=ntype,
        domain_id=did or nid,
        attributes=GraphAttributes(label=did or nid),
        metadata=GraphMetadata(created_by="test"),
    )


def _edge(eid: str, src: str, tgt: str) -> GraphEdge:
    return GraphEdge(
        edge_id=GraphEdgeId(value=eid),
        edge_type=GraphEdgeType.REFERENCES,
        source_node=GraphNodeId(value=src),
        target_node=GraphNodeId(value=tgt),
    )


def _link(gid: str) -> ProvenanceLink:
    return ProvenanceLink(
        graph_node_id=GraphNodeId(value=gid),
        source=ProvenanceSource(source_type=ProvenanceSourceType.DOCUMENT, source_id="doc"),
    )


def _snap(nodes=(), edges=(), links=()):
    return KnowledgeSnapshot(
        graph=KnowledgeGraph(nodes=tuple(nodes), edges=tuple(edges)),
        provenance=KnowledgeProvenance(
            provenance_id=ProvenanceId.generate(),
            chain=ProvenanceChain(links=tuple(links)),
        ),
        explanation=GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="root"),
        ),
    )


class TestRepairSnapshot:

    def test_remove_broken_edge(self):
        snap = _snap(
            nodes=(_node("n1", "ent-a"),),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        repaired, actions = _repair_snapshot(snap, check_snapshot_consistency(snap).violations)
        assert len(actions) == 1
        assert actions[0].action_type == "remove_broken_edge"
        assert len(repaired.graph.edges) == 0  # edge removed

    def test_remove_duplicate_node(self):
        snap = _snap(
            nodes=(_node("n1", "ent-dup"), _node("n2", "ent-dup")),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"), _link("n2")),
        )
        repaired, actions = _repair_snapshot(snap, check_snapshot_consistency(snap).violations)
        assert any(a.action_type == "remove_duplicate" for a in actions)

    def test_valid_snapshot_no_actions(self):
        snap = _snap(
            nodes=(_node("n1", "ent-a"), _node("n2", "ent-b")),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"), _link("n2")),
        )
        repaired, actions = _repair_snapshot(snap, check_snapshot_consistency(snap).violations)
        assert len(actions) == 0
        assert len(repaired.graph.nodes) == 2

    def test_repaired_snapshot_passes_consistency(self):
        snap = _snap(
            nodes=(_node("n1", "ent-a"),),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        repaired, _ = _repair_snapshot(snap, check_snapshot_consistency(snap).violations)
        result = check_snapshot_consistency(repaired)
        # No errors (broken edge removed), but node is now orphan → warning
        assert result.errors == 0
        assert result.is_consistent is False  # orphan is a warning


class TestBuildRecoveryPlan:

    def test_plan_with_violations(self):
        snap = _snap(
            nodes=(_node("n1", "ent-a"),),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        plan = build_recovery_plan("rev-001", snap)
        assert plan.violations_count >= 1
        assert plan.actionable_count >= 1
        assert plan.governance_status == "CHECK_REQUIRED"

    def test_plan_no_violations(self):
        snap = _snap(
            nodes=(_node("n1", "ent-a"), _node("n2", "ent-b")),
            edges=(_edge("e1", "n1", "n2"),),
            links=(_link("n1"), _link("n2")),
        )
        plan = build_recovery_plan("rev-valid", snap)
        assert plan.violations_count == 0
        assert plan.actionable_count == 0
        assert plan.governance_status == "APPROVED"

    def test_plan_with_governance_rejected(self):
        snap = _snap(
            nodes=(_node("n1", "ent-a"),),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        gov = GovernanceDecision(
            decision="REJECTED", reason="Blocked", based_on_trust="INVALID",
        )
        plan = build_recovery_plan("rev-001", snap, governance_decision=gov)
        assert plan.governance_status == "REJECTED"


class TestExecuteRecovery:

    def _make_record(self, rev_id: str, snap) -> Any:
        rev = KnowledgeRevision(
            revision_id=KnowledgeRevisionId(value=rev_id),
            revision_number=KnowledgeRevisionNumber(number=1),
            snapshot=snap,
            metadata=KnowledgeRevisionMetadata(
                created_at=datetime(2026, 1, 1), created_by="test", reason="original",
            ),
        )
        return rev

    def test_execute_requires_approval(self):
        snap = _snap(
            nodes=(_node("n1", "ent-a"),),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        rev = self._make_record("rev-bad", snap)
        from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
        record = KnowledgeRevisionRecord(
            revision=rev, explanation=rev.snapshot.explanation, source_document_id="doc",
        )
        gov = GovernanceDecision(
            decision="REJECTED", reason="Blocked", based_on_trust="INVALID",
        )
        result = execute_recovery(record, gov)
        assert result.success is False
        assert "blocked" in result.message.lower()

    def test_execute_approval_creates_result(self):
        snap = _snap(
            nodes=(_node("n1", "ent-a"),),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        rev = self._make_record("rev-repair", snap)
        from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
        record = KnowledgeRevisionRecord(
            revision=rev, explanation=rev.snapshot.explanation, source_document_id="doc",
        )
        gov = GovernanceDecision(
            decision="APPROVED", reason="Safe to repair", based_on_trust="VALID",
        )
        result = execute_recovery(record, gov)
        assert result.success is True
        assert result.recovery_revision_id != ""
        assert result.actions_performed >= 1

    def test_old_revision_unchanged(self):
        """Original revision's snapshot is not modified by repair."""
        snap = _snap(
            nodes=(_node("n1", "ent-a"),),
            edges=(_edge("e1", "n1", "missing"),),
            links=(_link("n1"),),
        )
        original_node_count = len(snap.graph.nodes)
        original_edge_count = len(snap.graph.edges)

        rev = self._make_record("rev-immutable", snap)
        from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
        record = KnowledgeRevisionRecord(
            revision=rev, explanation=rev.snapshot.explanation, source_document_id="doc",
        )
        gov = GovernanceDecision(
            decision="APPROVED", reason="Safe", based_on_trust="VALID",
        )
        execute_recovery(record, gov)

        # Original unchanged
        assert len(rev.snapshot.graph.nodes) == original_node_count
        assert len(rev.snapshot.graph.edges) == original_edge_count
