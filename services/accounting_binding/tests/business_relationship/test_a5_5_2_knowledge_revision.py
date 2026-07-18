"""
Tests — Knowledge Revision Services Phase A5.5.2.

Covers: RevisionSnapshotFactory, RevisionReferenceFactory,
        RevisionBuilder, RevisionIntegrityChecker.

ALL services: stateless, deterministic, immutable outputs.
NO rollback/restore/merge/diff/apply/replay/compare/patch/update.
"""
from __future__ import annotations

from datetime import datetime
import pytest

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata
from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_result import KnowledgeRevisionResult, KnowledgeRevisionReport
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.revision_reference import RevisionReference
from domain.business_relationship.revision_snapshot_factory import RevisionSnapshotFactory
from domain.business_relationship.revision_reference_factory import RevisionReferenceFactory
from domain.business_relationship.revision_builder import RevisionBuilder
from domain.business_relationship.revision_integrity import RevisionIntegrityChecker, RevisionIntegrityReport
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_attributes import GraphMetadata, GraphAttributes
from domain.business_relationship.kg_identifiers import GraphNodeId
from domain.business_relationship.kg_enums import GraphNodeType
from domain.business_relationship.kg_node import GraphNode
from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.kg_provenance_metadata import ProvenanceMetadata
from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_metadata import ExplanationMetadata

# ─── Deterministic test values ───
FIXED_DT = datetime(2026, 7, 7, 17, 0, 0, 0)
FIXED_SV = 1
FIXED_RH = 0


# ─── Helpers ───

def make_graph(nodes: int = 1, edges: int = 0) -> KnowledgeGraph:
    test_nodes = tuple(
        GraphNode(
            node_id=GraphNodeId(value=f"n{i}"),
            node_type=GraphNodeType.ENTITY,
            domain_id=str(i),
            attributes=GraphAttributes(label=f"Node{i}", tags=()),
            metadata=GraphMetadata(
                created_at=FIXED_DT,
                created_by='',
                knowledge_revision_hint=FIXED_RH,
                schema_version=FIXED_SV,
            ),
        )
        for i in range(nodes)
    )
    return KnowledgeGraph(nodes=test_nodes, edges=())


def make_provenance() -> KnowledgeProvenance:
    return KnowledgeProvenance(
        provenance_id=ProvenanceId(value="prov-1"),
        metadata=ProvenanceMetadata(
            created_at=FIXED_DT,
            source_count=1,
            confidence=1.0,
            revision_hint=FIXED_RH,
        ),
    )


def make_explanation() -> GraphExplanation:
    return GraphExplanation(
        explanation_id=ExplanationId(value="exp-1"),
        graph_node_id=GraphNodeId(value="n1"),
        metadata=ExplanationMetadata(
            created_at=FIXED_DT,
            created_by='',
            knowledge_revision_hint=FIXED_RH,
            schema_version=FIXED_SV,
        ),
    )


# ─── RevisionSnapshotFactory Tests ───

class TestRevisionSnapshotFactory:
    def test_empty(self):
        factory = RevisionSnapshotFactory()
        snapshot = factory.empty()
        assert isinstance(snapshot, KnowledgeSnapshot)
        assert snapshot.total_nodes == 0
        assert snapshot.total_edges == 0

    def test_from_graph(self):
        graph = make_graph(nodes=2)
        snapshot = RevisionSnapshotFactory.from_graph(graph)
        assert snapshot.graph is graph
        assert snapshot.total_nodes == 2

    def test_from_provenance(self):
        prov = make_provenance()
        snapshot = RevisionSnapshotFactory.from_provenance(prov)
        assert snapshot.provenance is prov

    def test_from_explanation(self):
        exp = make_explanation()
        snapshot = RevisionSnapshotFactory.from_explanation(exp)
        assert snapshot.explanation is exp

    def test_create(self):
        graph = make_graph(nodes=3)
        prov = make_provenance()
        snapshot = RevisionSnapshotFactory.create(graph=graph, provenance=prov)
        assert snapshot.graph is graph
        assert snapshot.provenance is prov
        assert snapshot.explanation is None

    def test_deterministic(self):
        graph = make_graph(nodes=1)
        snapshot1 = RevisionSnapshotFactory.from_graph(graph)
        snapshot2 = RevisionSnapshotFactory.from_graph(graph)
        assert snapshot1 == snapshot2


# ─── RevisionReferenceFactory Tests ───

class TestRevisionReferenceFactory:
    def test_parent(self):
        parent_id = KnowledgeRevisionId(value="p1")
        derived_id = KnowledgeRevisionId(value="d1")
        ref = RevisionReferenceFactory.parent(parent_id, derived_id)
        assert ref.parent_revision_id == parent_id
        assert ref.derived_revision_id == derived_id

    def test_derived(self):
        parent_id = KnowledgeRevisionId(value="p1")
        derived_id = KnowledgeRevisionId(value="d1")
        ref = RevisionReferenceFactory.derived(derived_id, parent_id)
        assert ref.parent_revision_id == parent_id
        assert ref.derived_revision_id == derived_id

    def test_branched(self):
        source_id = KnowledgeRevisionId(value="src")
        branch_id = KnowledgeRevisionId(value="branch")
        ref = RevisionReferenceFactory.branched(branch_id, source_id)
        assert ref.parent_revision_id == source_id
        assert ref.derived_revision_id == branch_id

    def test_deterministic(self):
        parent_id = KnowledgeRevisionId(value="p1")
        derived_id = KnowledgeRevisionId(value="d1")
        r1 = RevisionReferenceFactory.parent(parent_id, derived_id)
        r2 = RevisionReferenceFactory.parent(parent_id, derived_id)
        assert r1 == r2


# ─── RevisionIntegrityChecker Tests ───

class TestRevisionIntegrityChecker:
    def test_valid_revision(self):
        graph = make_graph(nodes=2)
        snapshot = RevisionSnapshotFactory.from_graph(graph)
        rid = KnowledgeRevisionId(value="r1")
        rn = KnowledgeRevisionNumber(number=1)
        meta = KnowledgeRevisionMetadata(created_at=FIXED_DT)
        revision = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)
        parent_id = KnowledgeRevisionId(value="p1")
        ref = RevisionReferenceFactory.parent(parent_id, rid)

        report = RevisionIntegrityChecker.check(revision, references=(ref,))
        assert not report.missing_snapshot
        assert not report.missing_metadata
        assert not report.missing_reference
        assert not report.empty_snapshot
        assert len(report.warnings) == 0

    def test_empty_snapshot_warning(self):
        snapshot = KnowledgeSnapshot.empty()
        rid = KnowledgeRevisionId(value="r1")
        rn = KnowledgeRevisionNumber(number=1)
        meta = KnowledgeRevisionMetadata(created_at=FIXED_DT)
        revision = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)
        parent_id = KnowledgeRevisionId(value="p1")
        ref = RevisionReferenceFactory.parent(parent_id, rid)

        report = RevisionIntegrityChecker.check(revision, references=(ref,))
        assert report.empty_snapshot

    def test_missing_reference_warning(self):
        graph = make_graph(nodes=2)
        snapshot = RevisionSnapshotFactory.from_graph(graph)
        rid = KnowledgeRevisionId(value="r1")
        rn = KnowledgeRevisionNumber(number=1)
        meta = KnowledgeRevisionMetadata(created_at=FIXED_DT)
        revision = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)

        report = RevisionIntegrityChecker.check(revision)
        assert report.missing_reference

    def test_warnings_only(self):
        """IntegrityChecker must ONLY produce warnings, never fix."""
        snapshot = KnowledgeSnapshot.empty()
        rid = KnowledgeRevisionId(value="r1")
        rn = KnowledgeRevisionNumber(number=1)
        meta = KnowledgeRevisionMetadata(created_at=FIXED_DT)
        revision = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)

        report = RevisionIntegrityChecker.check(revision)
        # Report must never modify or return the revision
        assert isinstance(report, RevisionIntegrityReport)
        assert not hasattr(report, 'fixed')
        assert not hasattr(report, 'patched')
        assert not hasattr(report, 'corrected')

    def test_no_fix_methods(self):
        """IntegrityChecker must NOT have fix/repair/correct methods."""
        assert not hasattr(RevisionIntegrityChecker, 'fix')
        assert not hasattr(RevisionIntegrityChecker, 'repair')
        assert not hasattr(RevisionIntegrityChecker, 'correct')
        assert not hasattr(RevisionIntegrityChecker, 'patch')


# ─── RevisionBuilder Tests ───

class TestRevisionBuilder:
    def test_build_empty_revision(self):
        builder = RevisionBuilder()
        graph = make_graph(nodes=0)

        result = builder.build(graph)

        assert isinstance(result, KnowledgeRevisionResult)
        assert isinstance(result.revision, KnowledgeRevision)
        assert isinstance(result.report, KnowledgeRevisionReport)
        assert result.report.revision_number == 0
        assert result.report.nodes_total == 0
        assert result.report.edges_total == 0

    def test_build_with_data(self):
        builder = RevisionBuilder()
        graph = make_graph(nodes=3)
        prov = make_provenance()
        exp = make_explanation()

        result = builder.build(
            graph,
            provenance=prov,
            explanation=exp,
            revision_number=1,
            created_by="test-user",
            reason="test build",
            document_count=5,
            entity_count=3,
        )

        assert result.report.revision_number == 1
        assert result.report.nodes_total == 3
        assert result.revision.revision_number.number == 1
        assert result.revision.metadata.created_by == "test-user"
        assert result.revision.metadata.document_count == 5

    def test_build_with_parent(self):
        builder = RevisionBuilder()
        graph = make_graph(nodes=1)
        parent_id = KnowledgeRevisionId(value="parent-1")

        result = builder.build(
            graph,
            parent_revision_id=parent_id,
            revision_number=2,
        )

        assert result.revision.revision_number.number == 2
        # Parent reference should be created
        assert len(result.warnings) == 0 or 'no references' not in ' '.join(result.warnings)

    def test_deterministic(self):
        """Same inputs must produce bit-identical revision structure (modulo generated IDs)."""
        builder = RevisionBuilder()
        graph = make_graph(nodes=2)
        prov = make_provenance()

        result1 = builder.build(graph, provenance=prov, revision_number=1)
        result2 = builder.build(graph, provenance=prov, revision_number=1)

        # RevisionIds are generated (different), but structure should match
        assert result1.report == result2.report
        assert result1.revision.revision_number == result2.revision.revision_number
        assert result1.revision.snapshot.total_nodes == result2.revision.snapshot.total_nodes
        assert result1.revision.snapshot.total_edges == result2.revision.snapshot.total_edges

    def test_immutable(self):
        """Builder must not modify input graph."""
        builder = RevisionBuilder()
        graph = make_graph(nodes=2)
        original_nodes = graph.node_count

        builder.build(graph)

        assert graph.node_count == original_nodes

    def test_no_rollback_methods(self):
        """Builder must NOT have rollback/restore/merge methods."""
        assert not hasattr(RevisionBuilder, 'rollback')
        assert not hasattr(RevisionBuilder, 'restore')
        assert not hasattr(RevisionBuilder, 'merge')
        assert not hasattr(RevisionBuilder, 'diff')
        assert not hasattr(RevisionBuilder, 'apply')
        assert not hasattr(RevisionBuilder, 'replay')
        assert not hasattr(RevisionBuilder, 'compare')
        assert not hasattr(RevisionBuilder, 'patch')
        assert not hasattr(RevisionBuilder, 'update')


# ─── KnowledgeRevisionResult Tests ───

class TestKnowledgeRevisionResult:
    def test_create(self):
        rid = KnowledgeRevisionId(value="r1")
        rn = KnowledgeRevisionNumber(number=1)
        snapshot = KnowledgeSnapshot.empty()
        meta = KnowledgeRevisionMetadata(created_at=FIXED_DT)
        revision = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)
        report = KnowledgeRevisionReport(revision_number=1)

        result = KnowledgeRevisionResult(revision=revision, report=report)
        assert result.revision is revision
        assert result.report is report
        assert result.warnings == ()

    def test_immutable(self):
        rid = KnowledgeRevisionId(value="r1")
        rn = KnowledgeRevisionNumber(number=1)
        snapshot = KnowledgeSnapshot.empty()
        meta = KnowledgeRevisionMetadata(created_at=FIXED_DT)
        revision = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)
        report = KnowledgeRevisionReport()
        result = KnowledgeRevisionResult(revision=revision, report=report)

        with pytest.raises(Exception):
            result.revision = KnowledgeRevision(
                revision_id=KnowledgeRevisionId(value="x"),
                revision_number=KnowledgeRevisionNumber(number=2),
                snapshot=KnowledgeSnapshot.empty(),
                metadata=KnowledgeRevisionMetadata(created_at=FIXED_DT),
            )

    def test_equality(self):
        rid = KnowledgeRevisionId(value="r1")
        rn = KnowledgeRevisionNumber(number=1)
        snapshot = KnowledgeSnapshot.empty()
        meta = KnowledgeRevisionMetadata(created_at=FIXED_DT)
        revision = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)
        report = KnowledgeRevisionReport(revision_number=1)

        r1 = KnowledgeRevisionResult(revision=revision, report=report)
        r2 = KnowledgeRevisionResult(revision=revision, report=report)
        assert r1 == r2


# ─── KnowledgeRevisionReport Tests ───

class TestKnowledgeRevisionReport:
    def test_empty(self):
        report = KnowledgeRevisionReport()
        assert report.revision_number == 0
        assert report.nodes_total == 0
        assert report.edges_total == 0
        assert report.warnings == ()

    def test_equality(self):
        r1 = KnowledgeRevisionReport(revision_number=1, nodes_total=10, warnings=("test",))
        r2 = KnowledgeRevisionReport(revision_number=1, nodes_total=10, warnings=("test",))
        assert r1 == r2
