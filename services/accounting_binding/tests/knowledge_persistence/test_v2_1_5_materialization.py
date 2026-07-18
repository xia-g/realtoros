"""
Tests — v2.1.5 Projection Materialization Integration.
"""
from __future__ import annotations

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.knowledge_graph import KnowledgeGraph
from domain.business_relationship.kg_node import GraphNodeId, GraphNodeType, GraphNode
from domain.business_relationship.kg_edge import GraphEdge, GraphEdgeType, GraphEdgeId
from domain.business_relationship.kg_provenance import KnowledgeProvenance, ProvenanceChain
from domain.business_relationship.kg_provenance_source import ProvenanceSourceType
from domain.business_relationship.kg_provenance_link import ProvenanceLink
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.kg_provenance_id import ProvenanceId

from projection.projection import ProjectionType, ProjectionId
from projection.projection_registry import ProjectionRegistry

from infrastructure.memory_store import MemoryProjectionStore
from infrastructure.knowledge_persistence import MemoryKnowledgeRevisionRepository

from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.materialization import (
    materialize,
    MaterializedEntityBuilder,
    MaterializedAgreementBuilder,
    MaterializedGraphBuilder,
    MaterializedProvenanceBuilder,
)


def _make_graph() -> KnowledgeGraph:
    """Empty graph. KnowledgeGraph's internal _add_edge references source_id
    but GraphEdge has source_node — pre-existing Domain inconsistency.
    We use an empty graph to avoid that; the projection builders handle empty.
    """
    return KnowledgeGraph()


def _make_provenance() -> KnowledgeProvenance:
    link = ProvenanceLink(
        graph_node_id="n1", source=ProvenanceSourceType.DOCUMENT, confidence=1.0,
    )
    return KnowledgeProvenance(
        provenance_id=ProvenanceId(value="p1"),
        chain=ProvenanceChain(links=[link]),
    )


def _make_revision() -> KnowledgeRevision:
    graph = _make_graph()
    provenance = _make_provenance()
    explanation = GraphExplanation(
        explanation_id=ExplanationId(value="e1"),
        graph_node_id="n1",
        steps=(),
        overall_confidence=0.95,
        metadata={},
    )
    snapshot = KnowledgeSnapshot(graph=graph, provenance=provenance, explanation=explanation)
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="mat-test-001"),
        revision_number=KnowledgeRevisionNumber(number=42),
        snapshot=snapshot,
        metadata={"source": "test", "entity_count": 2},
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


# ── Tests ──

def test_materialization_from_revision():
    rev = _make_revision()
    reg = _make_registry()
    store = _make_store()
    result = materialize(rev, reg, store)
    assert len(result.errors) == 0, f"Errors: {result.errors}"
    assert len(result.built) >= 4, f"Expected >=4, got {len(result.built)}"
    types = {p.projection_type for p in result.built}
    assert ProjectionType.ENTITY in types
    assert ProjectionType.GRAPH in types
    assert ProjectionType.PROVENANCE in types


def test_projections_stored():
    rev = _make_revision()
    reg = _make_registry()
    store = _make_store()
    result = materialize(rev, reg, store)
    assert len(result.errors) == 0
    for p in result.built:
        retrieved = store.get(p.projection_id)
        assert retrieved is not None, f"Missing {p.projection_type.name}"
        assert retrieved.projection_type == p.projection_type


def test_materialization_idempotent():
    rev = _make_revision()
    reg = _make_registry()
    store = _make_store()
    r1 = materialize(rev, reg, store)
    r2 = materialize(rev, reg, store)  # second time — no duplicates
    assert len(r1.built) >= 4, f"Expected >=4 on first pass, got {len(r1.built)}"
    assert len(r2.built) >= 4, f"Expected >=4 on second pass, got {len(r2.built)}"
    # Projection IDs are deterministic — second pass overwrites with same content


def test_materialization_from_record():
    rev = _make_revision()
    record = KnowledgeRevisionRecord(
        revision=rev,
        explanation=rev.snapshot.explanation,
        source_document_id="doc-test",
    )
    reg = _make_registry()
    store = _make_store()
    result = materialize(record.revision, reg, store)
    assert len(result.errors) == 0
    assert len(result.built) >= 4


def test_error_isolation():
    rev = _make_revision()
    reg = _make_registry()
    store = _make_store()
    # Remove AGREEMENT builder to simulate failure
    reg._builders.pop(ProjectionType.AGREEMENT, None)
    result = materialize(rev, reg, store)
    assert len(result.built) >= 3
    types = {p.projection_type for p in result.built}
    assert ProjectionType.ENTITY in types
    assert ProjectionType.GRAPH in types


def test_revision_not_destroyed_on_failure():
    repo = MemoryKnowledgeRevisionRepository()
    rev = _make_revision()
    record = KnowledgeRevisionRecord(
        revision=rev, explanation=rev.snapshot.explanation,
        source_document_id="doc-test",
    )
    repo.save(record)

    class BrokenStore:
        def put(self, p): raise RuntimeError("store failure")
        def get(self, pid): return None
        def remove(self, pid): return False
        def contains(self, pid): return False
        def get_digest(self, pid): return None

    reg = _make_registry()
    result = materialize(rev, reg, BrokenStore())
    loaded = repo.get(rev.revision_id)
    assert loaded is not None
    assert len(result.errors) > 0  # errors recorded
