"""
Tests — v2.1.5 Query Runtime Verification + Explainability Trace.
"""
from __future__ import annotations

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.knowledge_graph import KnowledgeGraph
from domain.business_relationship.kg_provenance import KnowledgeProvenance, ProvenanceChain
from domain.business_relationship.kg_provenance_source import ProvenanceSourceType
from domain.business_relationship.kg_provenance_link import ProvenanceLink
from domain.business_relationship.kg_provenance_id import ProvenanceId
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId

from projection.projection import ProjectionType, ProjectionId

from infrastructure.memory_store import MemoryProjectionStore
from infrastructure.knowledge_persistence import MemoryKnowledgeRevisionRepository

from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.materialization import materialize
from application.knowledge_persistence.query_verification import (
    QueryExplainabilityResolver,
    QueryTrace,
    run_diagnostic_queries,
    QueryResult,
)
from application.knowledge_persistence.runtime_integration import (
    run_v21_5_pipeline,
    build_pipeline_components,
)
from application.knowledge_persistence.materialization import (
    MaterializedEntityBuilder,
    MaterializedAgreementBuilder,
    MaterializedGraphBuilder,
    MaterializedProvenanceBuilder,
)
from projection.projection_registry import ProjectionRegistry
from projection.build_plan import BuildPlan, BuildStep


def _make_minimal_revision(rid: str = "qr-test-001") -> KnowledgeRevision:
    prov = KnowledgeProvenance(
        provenance_id=ProvenanceId(value="p1"),
        chain=ProvenanceChain(links=[
            ProvenanceLink(graph_node_id="n1", source=ProvenanceSourceType.DOCUMENT, confidence=1.0),
        ]),
    )
    exp = GraphExplanation(
        explanation_id=ExplanationId(value="e1"), graph_node_id="n1",
        steps=(),
        overall_confidence=0.95,
        metadata={},
    )
    snapshot = KnowledgeSnapshot(
        graph=KnowledgeGraph(),
        provenance=prov,
        explanation=exp,
    )
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value=rid),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=snapshot,
        metadata={"source": "test", "entity_count": 0},
    )


def _make_registry() -> ProjectionRegistry:
    reg = ProjectionRegistry()
    reg.register(MaterializedEntityBuilder())
    reg.register(MaterializedAgreementBuilder())
    reg.register(MaterializedGraphBuilder())
    reg.register(MaterializedProvenanceBuilder())
    return reg


def _make_store() -> MemoryProjectionStore:
    return MemoryProjectionStore()


# ── Tests: Query Explainability Resolver ──

def test_resolver_resolves_revision():
    rev = _make_minimal_revision("resolver-1")
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-1",
    )
    repo.save(record)
    resolver = QueryExplainabilityResolver(repo)
    trace = resolver.resolve("resolver-1")
    assert trace is not None
    assert trace.source_document_id == "doc-1"
    assert trace.explainability_available is True
    assert trace.provenance_available is True


def test_resolver_returns_none_for_missing():
    repo = MemoryKnowledgeRevisionRepository()
    resolver = QueryExplainabilityResolver(repo)
    assert resolver.resolve("nonexistent") is None


def test_resolver_with_result():
    rev = _make_minimal_revision("resolver-2")
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-2",
    )
    repo.save(record)
    resolver = QueryExplainabilityResolver(repo)
    trace = resolver.resolve_with_result("resolver-2", "ENTITY", "2 entities", 2)
    assert trace.query_target == "ENTITY"
    assert trace.result_count == 2
    assert trace.source_document_id == "doc-2"


# ── Tests: Diagnostic Queries ──

def test_entity_query_returns_result():
    rev = _make_minimal_revision()
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-query",
    )
    repo.save(record)
    materialize(rev, reg, store)

    batch = run_diagnostic_queries(store, repo, "qr-test-001", "doc-query")
    entity_results = [r for r in batch.results if r.target == "ENTITY"]
    assert len(entity_results) == 1
    assert entity_results[0].success


def test_agreement_query_returns_result():
    rev = _make_minimal_revision()
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-query",
    )
    repo.save(record)
    materialize(rev, reg, store)

    batch = run_diagnostic_queries(store, repo, "qr-test-001", "doc-query")
    agreement_results = [r for r in batch.results if r.target == "AGREEMENT"]
    assert len(agreement_results) == 1
    assert agreement_results[0].success


def test_graph_query_returns_result():
    rev = _make_minimal_revision()
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-query",
    )
    repo.save(record)
    materialize(rev, reg, store)

    batch = run_diagnostic_queries(store, repo, "qr-test-001", "doc-query")
    graph_results = [r for r in batch.results if r.target == "GRAPH"]
    assert len(graph_results) == 1
    assert graph_results[0].success


def test_all_three_queries_execute():
    rev = _make_minimal_revision()
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-query",
    )
    repo.save(record)
    materialize(rev, reg, store)

    batch = run_diagnostic_queries(store, repo, "qr-test-001", "doc-query")
    assert len(batch.results) == 3
    assert all(r.success for r in batch.results)


def test_query_uses_store_not_domain():
    """Query uses MemoryProjectionStore, not KnowledgeRevision directly."""
    rev = _make_minimal_revision()
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-query",
    )
    repo.save(record)
    materialize(rev, reg, store)

    batch = run_diagnostic_queries(store, repo, "qr-test-001", "doc-query")
    # All should succeed because projections exist in store
    assert all(r.success for r in batch.results)


def test_query_trace_revision_id():
    rev = _make_minimal_revision("trace-rev")
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-trace",
    )
    repo.save(record)
    materialize(rev, reg, store)

    batch = run_diagnostic_queries(store, repo, "trace-rev", "doc-trace")
    for t in batch.traces:
        assert t.revision_id == "trace-rev"
        assert t.source_document_id == "doc-trace"
        assert t.revision_id or True  # revision_id always set


def test_explainability_available():
    rev = _make_minimal_revision()
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-exp",
    )
    repo.save(record)
    materialize(rev, reg, store)
    batch = run_diagnostic_queries(store, repo, str(rev.revision_id.value), "doc-exp")
    for t in batch.traces:
        assert t.explainability_available is True


def test_provenance_available():
    rev = _make_minimal_revision()
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-prov",
    )
    repo.save(record)
    materialize(rev, reg, store)
    batch = run_diagnostic_queries(store, repo, str(rev.revision_id.value), "doc-prov")
    for t in batch.traces:
        assert t.provenance_available is True
        assert t.provenance_chain_length >= 1


def test_source_document_available():
    rev = _make_minimal_revision()
    reg = _make_registry()
    store = _make_store()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-src",
    )
    repo.save(record)
    materialize(rev, reg, store)
    batch = run_diagnostic_queries(store, repo, str(rev.revision_id.value), "doc-src")
    for t in batch.traces:
        assert t.source_document_id == "doc-src"


def test_query_failure_does_not_delete_revision():
    rev = _make_minimal_revision("fail-safe")
    reg = _make_registry()
    repo = MemoryKnowledgeRevisionRepository()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-fail",
    )
    repo.save(record)
    # Don't materialize — queries will find no projections
    store = _make_store()
    batch = run_diagnostic_queries(store, repo, "fail-safe", "doc-fail")
    # Revision still exists
    loaded = repo.get(rev.revision_id)
    assert loaded is not None
    assert loaded.source_document_id == "doc-fail"


# ── Test: run_v21_5_pipeline ──

def test_full_pipeline_with_mock_result():
    rev = _make_minimal_revision("full-pipe")
    pipeline_result = {
        "document_id": "doc-pipe",
        "revision": rev,
        "explanation": rev.snapshot.explanation,
    }
    reg, plan, store, repo = build_pipeline_components()
    result = run_v21_5_pipeline(pipeline_result, reg, plan, store, repo)
    assert result["status"] == "ok"
    assert result.get("projection_count", 0) >= 4
    assert "queries" in result
    assert result["provenance_available"] is True
    assert result["explainability_available"] is True
    assert result["source_trace_available"] is True
