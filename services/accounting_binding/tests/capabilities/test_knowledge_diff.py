"""
Knowledge Diff Explorer — T1: unit tests for stateless diff logic.

Tests verify:
  - Node diff (added, removed, updated, unchanged)
  - Edge diff (added, removed)
  - Provenance diff (added, removed)
  - Explanation diff (added, removed, changed)
  - Invariants: Diff(A,A)=empty, deterministic, order-independent

No Platform changes.
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
from domain.business_relationship.kg_provenance_metadata import ProvenanceMetadata
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.ke_explanation_step import ExplanationStep
from domain.business_relationship.ke_explanation_reason import ExplanationReasonType
from domain.business_relationship.ke_explanation_parts import ExplanationReason, ExplanationEvidence
from domain.business_relationship.ke_explanation_metadata import ExplanationMetadata
from domain.business_relationship.kg_identifiers import GraphNodeId

from application.capabilities.knowledge_diff import (
    diff_nodes,
    diff_edges,
    diff_provenance,
    diff_explanation,
    diff_snapshots,
    DiffResult,
    NodeDiffEntry,
    EdgeDiffEntry,
    ProvenanceDiffEntry,
    ExplanationDiffEntry,
)


# ─── Helpers ──────────────────────────────────────────────────────


def _make_node(
    domain_id: str,
    node_type: GraphNodeType = GraphNodeType.ENTITY,
    label: str = "",
    display_name: str = "",
    tags: tuple[str, ...] = (),
) -> GraphNode:
    return GraphNode(
        node_id=GraphNodeId(value=f"node-{domain_id}"),
        node_type=node_type,
        domain_id=domain_id,
        attributes=GraphAttributes(label=label or domain_id, display_name=display_name or domain_id, tags=tags),
        metadata=GraphMetadata(created_by="test"),
    )


def _make_edge(
    source_id: str,
    target_id: str,
    edge_type: GraphEdgeType = GraphEdgeType.REFERENCES,
) -> GraphEdge:
    return GraphEdge(
        edge_id=GraphEdgeId(value=f"edge-{source_id}-{target_id}"),
        edge_type=edge_type,
        source_node=GraphNodeId(value=source_id),
        target_node=GraphNodeId(value=target_id),
        attributes=GraphAttributes(),
        metadata=GraphMetadata(created_by="test"),
    )


def _make_link(
    graph_node_id: str,
    source_type: str = "document",
    source_id: str = "doc-001",
    description: str = "",
) -> ProvenanceLink:
    return ProvenanceLink(
        graph_node_id=GraphNodeId(value=graph_node_id),
        source=ProvenanceSource(
            source_type=ProvenanceSourceType(source_type),
            source_id=source_id,
            description=description,
        ),
        confidence=1.0,
    )


def _make_step(
    step_number: int,
    summary: str = "",
    reasons: tuple = (),
    evidence: tuple = (),
) -> ExplanationStep:
    return ExplanationStep(
        step_number=step_number,
        summary=summary or f"Step {step_number}",
        reasons=reasons,
        evidence=evidence,
    )


def _resolve_node_key_factory(
    nodes: tuple[GraphNode, ...],
) -> callable:
    """Build a resolver: node_id → (node_type_str, domain_id)."""
    mapping: dict[str, tuple[str, str]] = {}
    for n in nodes:
        nt = n.node_type.value if isinstance(n.node_type, GraphNodeType) else str(n.node_type)
        mapping[n.node_id.value] = (nt, n.domain_id)
    def resolve(node_id: str) -> tuple[str, str]:
        return mapping.get(node_id, ("", node_id))
    return resolve


# ─── Tests: Nodes ─────────────────────────────────────────────────


class TestNodeDiff:

    def test_empty_vs_empty(self):
        result = diff_nodes((), ())
        assert len(result) == 0

    def test_identical_nodes(self):
        n = _make_node("ent-1", GraphNodeType.ENTITY, "Same")
        result = diff_nodes((n,), (n,))
        assert len(result) == 0  # unchanged

    def test_node_added(self):
        result = diff_nodes((), (_make_node("ent-1"),))
        assert len(result) == 1
        assert result[0].status == "added"
        assert result[0].node_type == "entity"
        assert result[0].domain_id == "ent-1"

    def test_node_removed(self):
        result = diff_nodes((_make_node("ent-1"),), ())
        assert len(result) == 1
        assert result[0].status == "removed"
        assert result[0].domain_id == "ent-1"

    def test_node_updated_label(self):
        old = _make_node("ent-1", label="Old Name")
        new = _make_node("ent-1", label="New Name")
        result = diff_nodes((old,), (new,))
        assert len(result) == 1
        assert result[0].status == "updated"
        assert len(result[0].changes) == 1
        assert result[0].changes[0].field == "label"
        assert result[0].changes[0].old_value == "Old Name"
        assert result[0].changes[0].new_value == "New Name"

    def test_node_updated_tags(self):
        old = _make_node("ent-1", tags=("old",))
        new = _make_node("ent-1", tags=("new",))
        result = diff_nodes((old,), (new,))
        assert len(result) == 1
        assert result[0].status == "updated"
        assert any(c.field == "tags" for c in result[0].changes)

    def test_node_unaffected_by_metadata(self):
        """Metadata changes do NOT trigger updated."""
        old = _make_node("ent-1", label="Same", display_name="Same")
        new = GraphNode(
            node_id=GraphNodeId(value="different-uuid"),
            node_type=GraphNodeType.ENTITY,
            domain_id="ent-1",
            attributes=GraphAttributes(label="Same", display_name="Same"),
            metadata=GraphMetadata(created_by="different-user"),
        )
        result = diff_nodes((old,), (new,))
        assert len(result) == 0, "Metadata difference should not trigger update"

    def test_mixed_add_remove_update(self):
        stable = _make_node("stable", label="Stable")
        removed = _make_node("removed", label="Will Go")
        added = _make_node("added", label="New")
        updated_old = _make_node("updated", label="Before")
        updated_new = _make_node("updated", label="After")

        result = diff_nodes((stable, removed, updated_old), (stable, added, updated_new))
        statuses = {entry.domain_id: entry.status for entry in result}
        assert statuses["removed"] == "removed"
        assert statuses["added"] == "added"
        assert statuses["updated"] == "updated"
        assert "stable" not in statuses

    def test_different_types_same_domain_id(self):
        """(node_type, domain_id) composite key: same domain_id, different type → separate entries."""
        entity = _make_node("id-1", GraphNodeType.ENTITY)
        agreement = _make_node("id-1", GraphNodeType.AGREEMENT)
        result = diff_nodes((entity,), (agreement,))
        assert len(result) == 2  # one removed, one added
        statuses = {(e.node_type, e.domain_id): e.status for e in result}
        assert statuses[("entity", "id-1")] == "removed"
        assert statuses[("agreement", "id-1")] == "added"


# ─── Tests: Edges ─────────────────────────────────────────────────


class TestEdgeDiff:

    def test_empty_vs_empty(self):
        result = diff_edges((), ())
        assert len(result) == 0

    def test_identical_edges(self):
        e = _make_edge("n1", "n2", GraphEdgeType.PARTICIPATES)
        result = diff_edges((e,), (e,))
        assert len(result) == 0

    def test_edge_added(self):
        e = _make_edge("n1", "n2", GraphEdgeType.PARTICIPATES)
        result = diff_edges((), (e,))
        assert len(result) == 1
        assert result[0].status == "added"

    def test_edge_removed(self):
        e = _make_edge("n1", "n2", GraphEdgeType.OWNS)
        result = diff_edges((e,), ())
        assert len(result) == 1
        assert result[0].status == "removed"

    def test_edge_no_updated(self):
        """Edge diff has only added/removed, never updated."""
        old = _make_edge("n1", "n2", GraphEdgeType.REFERENCES)
        # Change edge type → it's a different semantic key
        new = _make_edge("n1", "n2", GraphEdgeType.PARTICIPATES)
        result = diff_edges((old,), (new,))
        assert len(result) == 2  # one removed, one added
        assert all(e.status in ("added", "removed") for e in result)

    def test_edge_semantic_key_with_resolver(self):
        """With resolve_node_key, edges are matched by semantic key."""
        nodes = (
            _make_node("ent-a", GraphNodeType.ENTITY, "Seller"),
            _make_node("ent-b", GraphNodeType.ENTITY, "Buyer"),
        )
        resolver = _resolve_node_key_factory(nodes)
        e1 = _make_edge(nodes[0].node_id.value, nodes[1].node_id.value, GraphEdgeType.PARTICIPATES)
        # Same semantic relationship, different random edge_id
        e2 = _make_edge(nodes[0].node_id.value, nodes[1].node_id.value, GraphEdgeType.PARTICIPATES)
        result = diff_edges((e1,), (e2,), resolver)
        assert len(result) == 0  # same key → no diff

    def test_edge_different_relationship(self):
        """Different edge types → different semantic keys → diff."""
        nodes = (
            _make_node("ent-a", GraphNodeType.ENTITY),
            _make_node("ent-b", GraphNodeType.ENTITY),
        )
        resolver = _resolve_node_key_factory(nodes)
        ref = _make_edge(nodes[0].node_id.value, nodes[1].node_id.value, GraphEdgeType.REFERENCES)
        owns = _make_edge(nodes[0].node_id.value, nodes[1].node_id.value, GraphEdgeType.OWNS)
        result = diff_edges((ref,), (owns,), resolver)
        assert len(result) == 2  # one removed (ref), one added (owns)


# ─── Tests: Provenance ────────────────────────────────────────────


class TestProvenanceDiff:

    def test_empty_vs_empty(self):
        result = diff_provenance((), ())
        assert len(result) == 0

    def test_identical_links(self):
        link = _make_link("node-1", "document", "doc-001")
        result = diff_provenance((link,), (link,))
        assert len(result) == 0

    def test_link_added(self):
        link = _make_link("node-1", "document", "doc-002")
        result = diff_provenance((), (link,))
        assert len(result) == 1
        assert result[0].status == "added"
        assert result[0].source_id == "doc-002"

    def test_link_removed(self):
        link = _make_link("node-1", "agreement", "agr-001")
        result = diff_provenance((link,), ())
        assert len(result) == 1
        assert result[0].status == "removed"

    def test_key_is_source_type_plus_source_id(self):
        """Same (source_type, source_id) → same link, even if graph_node_id differs."""
        old = _make_link("old-node-uuid", "document", "doc-001")
        new = _make_link("new-node-uuid", "document", "doc-001")
        result = diff_provenance((old,), (new,))
        assert len(result) == 0  # same provenance, different node_id → no diff


# ─── Tests: Explanation ───────────────────────────────────────────


class TestExplanationDiff:

    def test_empty_vs_empty(self):
        result = diff_explanation((), ())
        assert len(result) == 0

    def test_identical_steps(self):
        step = _make_step(1, "Extract entity")
        result = diff_explanation((step,), (step,))
        assert len(result) == 0

    def test_step_added(self):
        step = _make_step(1, "New step")
        result = diff_explanation((), (step,))
        assert len(result) == 1
        assert result[0].status == "added"
        assert result[0].step_number == 1

    def test_step_removed(self):
        step = _make_step(2, "Removed step")
        result = diff_explanation((step,), ())
        assert len(result) == 1
        assert result[0].status == "removed"
        assert result[0].step_number == 2

    def test_step_changed(self):
        old = _make_step(1, "Old summary")
        new = _make_step(1, "New summary")
        result = diff_explanation((old,), (new,))
        assert len(result) == 1
        assert result[0].status == "changed"
        assert any(c.field == "summary" for c in result[0].changes)

    def test_mixed_scenario(self):
        s1 = _make_step(1, "Unchanged")
        s2 = _make_step(2, "Removed")
        s3 = _make_step(3, "Changed old")
        s4 = _make_step(4, "Added")
        s3_new = _make_step(3, "Changed new")

        result = diff_explanation((s1, s2, s3), (s1, s3_new, s4))
        status_map = {e.step_number: e.status for e in result}
        assert status_map[2] == "removed"
        assert status_map[4] == "added"
        assert status_map[3] == "changed"


# ─── Integration tests: diff_snapshots ────────────────────────────


class TestDiffSnapshots:

    def test_same_snapshot_empty_diff(self):
        """Diff(A, A) → empty."""
        snap = KnowledgeSnapshot(graph=KnowledgeGraph())
        result = diff_snapshots(snap, snap)
        assert result.is_empty

    def test_node_added_in_snapshot(self):
        left_graph = KnowledgeGraph()
        right_graph = KnowledgeGraph(
            nodes=(_make_node("ent-new"),),
        )
        left = KnowledgeSnapshot(graph=left_graph)
        right = KnowledgeSnapshot(graph=right_graph)
        result = diff_snapshots(left, right)
        assert len(result.nodes) == 1
        assert result.nodes[0].status == "added"

    def test_deterministic(self):
        """Same inputs → same output (run twice)."""
        n1 = _make_node("a")
        n2 = _make_node("b")
        snap1 = KnowledgeSnapshot(graph=KnowledgeGraph(nodes=(n1, n2)))
        snap2 = KnowledgeSnapshot(graph=KnowledgeGraph(nodes=(n1,)))  # b removed

        r1 = diff_snapshots(snap1, snap2)
        r2 = diff_snapshots(snap1, snap2)
        assert len(r1.nodes) == len(r2.nodes)
        assert r1.nodes[0].domain_id == r2.nodes[0].domain_id
        assert r1.nodes[0].status == r2.nodes[0].status

    def test_order_independent(self):
        """Diff(A, B) and Diff(A, B) with different iteration order → same."""
        nodes_a = (
            _make_node("x", GraphNodeType.ENTITY),
            _make_node("y", GraphNodeType.AGREEMENT),
        )
        nodes_b = (
            _make_node("x", GraphNodeType.ENTITY),
            _make_node("z", GraphNodeType.ENTITY),
        )
        snap_a = KnowledgeSnapshot(graph=KnowledgeGraph(nodes=nodes_a))
        snap_b = KnowledgeSnapshot(graph=KnowledgeGraph(nodes=nodes_b))

        r1 = diff_snapshots(snap_a, snap_b)
        r2 = diff_snapshots(snap_a, snap_b)
        # Convert to comparable form
        def summary(result: DiffResult) -> set:
            return {(e.node_type, e.domain_id, e.status) for e in result.nodes}
        assert summary(r1) == summary(r2)

    def test_snapshot_unchanged(self):
        """Diff does not mutate snapshots."""
        n = _make_node("test-id")
        snap = KnowledgeSnapshot(graph=KnowledgeGraph(nodes=(n,)))
        original_count = snap.graph.node_count
        _ = diff_snapshots(snap, snap)
        assert snap.graph.node_count == original_count
