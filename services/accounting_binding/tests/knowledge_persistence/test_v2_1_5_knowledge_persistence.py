"""
Tests — KnowledgeRevisionRecord + MemoryKnowledgeRevisionRepository.
"""
from __future__ import annotations

from datetime import datetime
from dataclasses import FrozenInstanceError

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId

from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.knowledge_revision_repository import (
    KnowledgeRevisionConflictError,
)
from infrastructure.knowledge_persistence import MemoryKnowledgeRevisionRepository


def make_minimal_revision(rev_id: str = "test-rev-001") -> KnowledgeRevision:
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value=rev_id),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=None,
        metadata={},
    )


def make_minimal_explanation(exp_id: str = "exp-001") -> GraphExplanation:
    return GraphExplanation(
        explanation_id=ExplanationId(value=exp_id),
        graph_node_id="",
        steps=(),
        overall_confidence=0.0,
        metadata={},
    )


# ── KnowledgeRevisionRecord ──

def test_record_is_immutable():
    r = KnowledgeRevisionRecord(
        revision=make_minimal_revision(),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
    )
    try:
        r.source_document_id = "changed"
        assert False, "should be frozen"
    except FrozenInstanceError:
        pass


def test_record_preserves_objects():
    rev = make_minimal_revision()
    exp = make_minimal_explanation()
    r = KnowledgeRevisionRecord(revision=rev, explanation=exp, source_document_id="doc-1")
    assert r.revision is rev
    assert r.explanation is exp


def test_record_value_based_equality():
    a = KnowledgeRevisionRecord(
        revision=make_minimal_revision(),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
        processing_job_id="job-1",
        created_at=datetime(2026, 1, 1),
    )
    b = KnowledgeRevisionRecord(
        revision=make_minimal_revision(),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
        processing_job_id="job-1",
        created_at=datetime(2026, 1, 1),
    )
    assert a == b


# ── MemoryKnowledgeRevisionRepository ──

def test_save_get_round_trip():
    repo = MemoryKnowledgeRevisionRepository()
    rev = make_minimal_revision()
    exp = make_minimal_explanation()
    record = KnowledgeRevisionRecord(revision=rev, explanation=exp, source_document_id="doc-1")
    repo.save(record)
    loaded = repo.get(rev.revision_id)
    assert loaded is not None
    assert loaded == record
    assert loaded.revision is rev


def test_get_missing_returns_none():
    repo = MemoryKnowledgeRevisionRepository()
    rid = KnowledgeRevisionId(value="nonexistent")
    assert repo.get(rid) is None


def test_get_by_document_id():
    repo = MemoryKnowledgeRevisionRepository()
    r1 = KnowledgeRevisionRecord(
        revision=make_minimal_revision("rev-1"),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
    )
    r2 = KnowledgeRevisionRecord(
        revision=make_minimal_revision("rev-2"),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
    )
    repo.save(r1)
    repo.save(r2)
    result = repo.get_by_document_id("doc-1")
    assert len(result) == 2
    assert r1 in result
    assert r2 in result


def test_get_by_document_id_empty():
    repo = MemoryKnowledgeRevisionRepository()
    assert repo.get_by_document_id("nonexistent") == ()


def test_idempotent_resave_same_record():
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=make_minimal_revision(),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
    )
    repo.save(record)
    repo.save(record)  # should not raise


def test_conflict_on_different_content():
    repo = MemoryKnowledgeRevisionRepository()
    r1 = KnowledgeRevisionRecord(
        revision=make_minimal_revision(),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
    )
    r2 = KnowledgeRevisionRecord(
        revision=make_minimal_revision(),
        explanation=make_minimal_explanation(),
        source_document_id="doc-2",
    )
    repo.save(r1)
    try:
        repo.save(r2)
        assert False, "should raise conflict"
    except KnowledgeRevisionConflictError:
        pass


def test_no_mutation():
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=make_minimal_revision(),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
    )
    repo.save(record)
    loaded = repo.get(record.revision.revision_id)
    assert loaded is not None
    assert loaded.source_document_id == "doc-1"
    assert len(repo) == 1


def test_multiple_documents():
    repo = MemoryKnowledgeRevisionRepository()
    r1 = KnowledgeRevisionRecord(
        revision=make_minimal_revision("rev-1"),
        explanation=make_minimal_explanation(),
        source_document_id="doc-1",
    )
    r2 = KnowledgeRevisionRecord(
        revision=make_minimal_revision("rev-2"),
        explanation=make_minimal_explanation(),
        source_document_id="doc-2",
    )
    repo.save(r1)
    repo.save(r2)
    assert len(repo.get_by_document_id("doc-1")) == 1
    assert len(repo.get_by_document_id("doc-2")) == 1
