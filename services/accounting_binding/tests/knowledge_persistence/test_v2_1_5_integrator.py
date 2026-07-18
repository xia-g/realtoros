"""
Tests — v2.1.5 KnowledgeRuntimeIntegrator production wiring.
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

from projection.projection import ProjectionType

from application.knowledge_persistence.integrator import (
    KnowledgeRuntimeIntegrator,
    KnowledgeRuntimeReport,
)


def _make_revision() -> KnowledgeRevision:
    prov = KnowledgeProvenance(
        provenance_id=ProvenanceId("p1"),
        chain=ProvenanceChain(links=[
            ProvenanceLink(graph_node_id="n1", source=ProvenanceSourceType.DOCUMENT, confidence=1.0),
        ]),
    )
    exp = GraphExplanation(
        explanation_id=ExplanationId("e1"), graph_node_id="n1",
        steps=(), overall_confidence=0.95, metadata={},
    )
    snap = KnowledgeSnapshot(
        graph=KnowledgeGraph(), provenance=prov, explanation=exp,
    )
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="int-test-001"),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=snap,
        metadata={},
    )


# ── Tests ──

def test_integrator_creates_singleton_instances():
    """Each integrator has its own repo + store."""
    i1 = KnowledgeRuntimeIntegrator()
    i2 = KnowledgeRuntimeIntegrator()
    assert i1.revision_repository is not i2.revision_repository
    assert i1.projection_store is not i2.projection_store


def test_integrate_saves_record():
    rev = _make_revision()
    pipeline_result = {"revision": rev, "explanation": rev.snapshot.explanation}
    integrator = KnowledgeRuntimeIntegrator()
    report = integrator.integrate(
        pipeline_result=pipeline_result,
        source_document_id="doc-int-1",
        processing_job_id="job-int-1",
    )
    assert report.status == "completed"
    assert report.persisted is True
    assert report.revision_id == "int-test-001"
    assert report.source_document_id == "doc-int-1"
    # Verify repository
    record = integrator.revision_repository.get(rev.revision_id)
    assert record is not None
    assert record.revision is rev
    assert record.explanation is rev.snapshot.explanation


def test_integrate_materializes_projections():
    rev = _make_revision()
    pipeline_result = {"revision": rev, "explanation": rev.snapshot.explanation}
    integrator = KnowledgeRuntimeIntegrator()
    report = integrator.integrate(
        pipeline_result=pipeline_result,
        source_document_id="doc-mat",
    )
    assert report.projection_count >= 4
    types = set(report.projection_types)
    assert ProjectionType.ENTITY.name in types
    assert ProjectionType.GRAPH.name in types
    assert ProjectionType.PROVENANCE.name in types


def test_integrate_runs_queries():
    rev = _make_revision()
    pipeline_result = {"revision": rev, "explanation": rev.snapshot.explanation}
    integrator = KnowledgeRuntimeIntegrator()
    report = integrator.integrate(
        pipeline_result=pipeline_result,
        source_document_id="doc-qr",
    )
    assert "entity" in report.query_result_counts
    assert "agreement" in report.query_result_counts
    assert "graph" in report.query_result_counts


def test_integrate_provenance_available():
    rev = _make_revision()
    pipeline_result = {"revision": rev, "explanation": rev.snapshot.explanation}
    integrator = KnowledgeRuntimeIntegrator()
    report = integrator.integrate(
        pipeline_result=pipeline_result,
        source_document_id="doc-prov",
    )
    assert report.provenance_available is True
    assert report.explanation_available is True
    assert report.source_trace_available is True


def test_integrate_idempotent():
    rev = _make_revision()
    pipeline_result = {"revision": rev, "explanation": rev.snapshot.explanation}
    integrator = KnowledgeRuntimeIntegrator()
    r1 = integrator.integrate(pipeline_result=pipeline_result, source_document_id="doc-idem")
    r2 = integrator.integrate(pipeline_result=pipeline_result, source_document_id="doc-idem")
    assert r1.status == "completed"
    assert r2.status == "completed"
    # Same revision — second call should be idempotent
    assert integrator.revision_repository.get(rev.revision_id) is not None


def test_shared_store_across_calls():
    integrator = KnowledgeRuntimeIntegrator()
    rev1 = _make_revision()  # revision_id = "int-test-001"
    integrator.integrate(
        pipeline_result={"revision": rev1, "explanation": rev1.snapshot.explanation},
        source_document_id="doc-multi-1",
    )
    # Create second revision with different id
    prov2 = KnowledgeProvenance(provenance_id=ProvenanceId("p2"), chain=ProvenanceChain(links=[ProvenanceLink(graph_node_id="n2", source=ProvenanceSourceType.DOCUMENT, confidence=1.0)]))
    exp2 = GraphExplanation(explanation_id=ExplanationId("e2"), graph_node_id="n2", steps=(), overall_confidence=0.9, metadata={})
    snap2 = KnowledgeSnapshot(graph=KnowledgeGraph(), provenance=prov2, explanation=exp2)
    rev2 = KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="multi-2"),
        revision_number=KnowledgeRevisionNumber(number=2),
        snapshot=snap2, metadata={},
    )
    integrator.integrate(
        pipeline_result={"revision": rev2, "explanation": rev2.snapshot.explanation},
        source_document_id="doc-multi-2",
    )
    # Both revisions should be in the same repo
    assert integrator.revision_repository.get(rev1.revision_id) is not None
    assert integrator.revision_repository.get(rev2.revision_id) is not None


def test_empty_pipeline_result_returns_error():
    integrator = KnowledgeRuntimeIntegrator()
    report = integrator.integrate(
        pipeline_result={},
        source_document_id="doc-empty",
    )
    assert report.status == "revision_extraction_failed"
    assert report.error_count >= 1
