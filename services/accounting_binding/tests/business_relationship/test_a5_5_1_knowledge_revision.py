"""
Tests — Knowledge Revision Domain Model Phase A5.5.1.

All models: immutable, no logic, no diff/merge/apply/rollback/restore/compare.
NO Domain Services. NO algorithms.
"""
from __future__ import annotations

from datetime import datetime
import pytest

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata
from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.revision_reference import RevisionReference
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


# ─── KnowledgeRevisionId Tests ───

class TestKnowledgeRevisionId:
    def test_generate(self):
        rid = KnowledgeRevisionId.generate()
        assert bool(rid)

    def test_from_string(self):
        rid = KnowledgeRevisionId.from_string("rev-1")
        assert rid.value == "rev-1"

    def test_equality(self):
        a = KnowledgeRevisionId(value="x")
        b = KnowledgeRevisionId(value="x")
        c = KnowledgeRevisionId(value="y")
        assert a == b
        assert a != c

    def test_hash(self):
        a = KnowledgeRevisionId(value="x")
        b = KnowledgeRevisionId(value="x")
        assert hash(a) == hash(b)

    def test_immutable(self):
        rid = KnowledgeRevisionId(value="x")
        with pytest.raises(Exception):
            rid.value = "y"


# ─── KnowledgeRevisionNumber Tests ───

class TestKnowledgeRevisionNumber:
    def test_validation(self):
        assert KnowledgeRevisionNumber(number=0) is not None
        assert KnowledgeRevisionNumber(number=1) is not None
        with pytest.raises(Exception):
            KnowledgeRevisionNumber(number=-1)

    def test_equality(self):
        assert KnowledgeRevisionNumber(number=1) == KnowledgeRevisionNumber(number=1)
        assert KnowledgeRevisionNumber(number=1) != KnowledgeRevisionNumber(number=2)

    def test_immutable(self):
        rn = KnowledgeRevisionNumber(number=1)
        with pytest.raises(Exception):
            rn.number = 2


# ─── KnowledgeSnapshot Tests ───

class TestKnowledgeSnapshot:
    def test_empty(self):
        snapshot = KnowledgeSnapshot.empty()
        assert snapshot.total_nodes == 0
        assert snapshot.total_edges == 0
        assert snapshot.graph is not None
        assert snapshot.provenance is not None
        assert snapshot.explanation is not None

    def test_with_graph(self):
        node = GraphNode(
            node_id=GraphNodeId(value="n1"),
            node_type=GraphNodeType.ENTITY,
            domain_id="d1",
            attributes=GraphAttributes(label="Entity", tags=()),
            metadata=GraphMetadata(
                created_at=FIXED_DT,
                created_by='',
                knowledge_revision_hint=FIXED_RH,
                schema_version=FIXED_SV,
            ),
        )
        graph = KnowledgeGraph(nodes=(node,), edges=())
        snapshot = KnowledgeSnapshot(graph=graph)
        assert snapshot.total_nodes == 1
        assert snapshot.total_edges == 0

    def test_immutable(self):
        snapshot = KnowledgeSnapshot.empty()
        with pytest.raises(Exception):
            snapshot.graph = KnowledgeGraph()

    def test_equality(self):
        meta = GraphMetadata(
            created_at=FIXED_DT,
            created_by='',
            knowledge_revision_hint=FIXED_RH,
            schema_version=FIXED_SV,
        )
        pid = ProvenanceId(value="p1")
        prov_meta = ProvenanceMetadata(
            created_at=FIXED_DT,
            source_count=0,
            confidence=1.0,
            revision_hint=FIXED_RH,
        )
        prev1 = KnowledgeProvenance(provenance_id=pid, metadata=prov_meta)
        prev2 = KnowledgeProvenance(provenance_id=pid, metadata=prov_meta)
        eid = ExplanationId(value="exp-fixed-id")
        exp1 = GraphExplanation(
            explanation_id=eid,
            graph_node_id=GraphNodeId(value="n1"),
            metadata=ExplanationMetadata(
                created_at=FIXED_DT,
                created_by='',
                knowledge_revision_hint=FIXED_RH,
                schema_version=FIXED_SV,
            ),
        )
        exp2 = GraphExplanation(
            explanation_id=eid,
            graph_node_id=GraphNodeId(value="n1"),
            metadata=ExplanationMetadata(
                created_at=FIXED_DT,
                created_by='',
                knowledge_revision_hint=FIXED_RH,
                schema_version=FIXED_SV,
            ),
        )

        snapshot1 = KnowledgeSnapshot(
            graph=KnowledgeGraph(metadata=meta),
            provenance=prev1,
            explanation=exp1,
        )
        snapshot2 = KnowledgeSnapshot(
            graph=KnowledgeGraph(metadata=meta),
            provenance=prev2,
            explanation=exp2,
        )
        # Full value-based equality — deterministic metadata ensures true equality
        assert snapshot1 == snapshot2


# ─── KnowledgeRevisionMetadata Tests ───

class TestKnowledgeRevisionMetadata:
    def test_empty(self):
        meta = KnowledgeRevisionMetadata()
        assert meta.created_at
        assert meta.created_by == ""
        assert meta.reason == ""

    def test_equality(self):
        meta1 = KnowledgeRevisionMetadata(
            created_at=FIXED_DT,
            created_by="user",
            reason="test",
            document_count=5,
            entity_count=3,
            graph_digest_hint="abc123",
        )
        meta2 = KnowledgeRevisionMetadata(
            created_at=FIXED_DT,
            created_by="user",
            reason="test",
            document_count=5,
            entity_count=3,
            graph_digest_hint="abc123",
        )
        assert meta1 == meta2

    def test_immutable(self):
        meta = KnowledgeRevisionMetadata()
        with pytest.raises(Exception):
            meta.created_by = "hacker"


# ─── RevisionReference Tests ───

class TestRevisionReference:
    def test_creation(self):
        parent = KnowledgeRevisionId(value="p1")
        derived = KnowledgeRevisionId(value="d1")
        ref = RevisionReference(parent_revision_id=parent, derived_revision_id=derived)
        assert ref.parent_revision_id == parent
        assert ref.derived_revision_id == derived

    def test_equality(self):
        parent = KnowledgeRevisionId(value="p1")
        derived = KnowledgeRevisionId(value="d1")
        ref1 = RevisionReference(parent_revision_id=parent, derived_revision_id=derived)
        ref2 = RevisionReference(parent_revision_id=parent, derived_revision_id=derived)
        assert ref1 == ref2

    def test_immutable(self):
        parent = KnowledgeRevisionId(value="p1")
        derived = KnowledgeRevisionId(value="d1")
        ref = RevisionReference(parent_revision_id=parent, derived_revision_id=derived)
        with pytest.raises(Exception):
            ref.parent_revision_id = KnowledgeRevisionId(value="p2")

    def test_no_navigation_methods(self):
        """RevisionReference must NOT have navigation/traversal methods."""
        parent = KnowledgeRevisionId(value="p1")
        derived = KnowledgeRevisionId(value="d1")
        ref = RevisionReference(parent_revision_id=parent, derived_revision_id=derived)
        assert not hasattr(ref, 'navigate')
        assert not hasattr(ref, 'traverse')
        assert not hasattr(ref, 'find')


# ─── KnowledgeRevision Tests ───

class TestKnowledgeRevision:
    def test_creation(self):
        rid = KnowledgeRevisionId(value="rev-1")
        rn = KnowledgeRevisionNumber(number=1)
        snapshot = KnowledgeSnapshot.empty()
        meta = KnowledgeRevisionMetadata()
        rev = KnowledgeRevision(
            revision_id=rid,
            revision_number=rn,
            snapshot=snapshot,
            metadata=meta,
        )
        assert rev.revision_id == rid
        assert rev.revision_number == rn
        assert rev.snapshot is snapshot
        assert rev.metadata is meta

    def test_equality(self):
        rid = KnowledgeRevisionId(value="x")
        rn = KnowledgeRevisionNumber(number=1)
        meta = KnowledgeRevisionMetadata(
            created_at=FIXED_DT,
            created_by="",
            reason="",
            document_count=0,
            entity_count=0,
            graph_digest_hint="",
        )
        snapshot = KnowledgeSnapshot.empty()
        rev1 = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)
        rev2 = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)
        assert rev1 == rev2

    def test_immutable(self):
        rid = KnowledgeRevisionId.generate()
        rn = KnowledgeRevisionNumber(number=1)
        snapshot = KnowledgeSnapshot.empty()
        meta = KnowledgeRevisionMetadata()
        rev = KnowledgeRevision(revision_id=rid, revision_number=rn, snapshot=snapshot, metadata=meta)
        with pytest.raises(Exception):
            rev.snapshot = KnowledgeSnapshot.empty()

    def test_no_diff_methods(self):
        """KnowledgeRevision must NOT have diff/merge/apply/rollback/restore/compare methods."""
        rid = KnowledgeRevisionId.generate()
        rn = KnowledgeRevisionNumber(number=1)
        rev = KnowledgeRevision(
            revision_id=rid,
            revision_number=rn,
            snapshot=KnowledgeSnapshot.empty(),
            metadata=KnowledgeRevisionMetadata(),
        )
        assert not hasattr(rev, 'diff')
        assert not hasattr(rev, 'merge')
        assert not hasattr(rev, 'apply')
        assert not hasattr(rev, 'rollback')
        assert not hasattr(rev, 'restore')
        assert not hasattr(rev, 'compare')

    def test_no_navigation_methods(self):
        """RevisionReference must NOT have navigation/traversal methods."""
        parent = KnowledgeRevisionId(value="p1")
        derived = KnowledgeRevisionId(value="d1")
        ref = RevisionReference(parent_revision_id=parent, derived_revision_id=derived)
        assert not hasattr(ref, 'navigate')
        assert not hasattr(ref, 'traverse')
        assert not hasattr(ref, 'find')
