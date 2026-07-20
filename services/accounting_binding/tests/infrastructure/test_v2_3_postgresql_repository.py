"""
v2.3 — PostgreSQL KnowledgeRevisionRepository integration tests.

Tests require a running PostgreSQL with the realtoros database.
Uses psycopg2 directly. DSN from backend.config.settings.

Run: python3 -m pytest services/accounting_binding/tests/infrastructure/test_v2_3_postgresql_repository.py -v
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
# Allow import of backend.config for DSN
sys.path.insert(0, "/home/xiag/real-estate-os")

import uuid
from datetime import datetime

import pytest

from backend.config import settings

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata
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

from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.knowledge_revision_repository import (
    KnowledgeRevisionConflictError,
)

from infrastructure.knowledge_persistence.postgresql_knowledge_revision_repository import (
    PostgreSQLKnowledgeRevisionRepository,
)


# ── Fixtures ──────────────────────────────────────────────────────

DSN = settings.DATABASE_SYNC_URL


@pytest.fixture
def repo():
    """Create a clean PostgreSQL repository for each test."""
    r = PostgreSQLKnowledgeRevisionRepository(dsn=DSN)
    r.delete_all()
    yield r
    r.delete_all()
    if r._connection is None:
        pass  # connection-per-op already closed


def _make_full_revision(doc_id: str = "test-doc") -> KnowledgeRevision:
    """Create a fully populated KnowledgeRevision for testing."""
    # Graph with nodes and edges
    node_1 = GraphNode(
        node_id=GraphNodeId(value="ent:org-1"),
        node_type=GraphNodeType.ENTITY,
        domain_id="org-1",
        attributes=GraphAttributes(label="ООО Продавец", display_name="Продавец"),
        metadata=GraphMetadata(created_by="test", schema_version=1),
    )
    node_2 = GraphNode(
        node_id=GraphNodeId(value="agr:sale-1"),
        node_type=GraphNodeType.AGREEMENT,
        domain_id="agr-1",
        attributes=GraphAttributes(label="Договор купли-продажи", tags=("sale", "dkp")),
        metadata=GraphMetadata(created_by="test"),
    )
    edge = GraphEdge(
        edge_id=GraphEdgeId(value=str(uuid.uuid4())),
        edge_type=GraphEdgeType.PARTICIPATES,
        source_node=node_1.node_id,
        target_node=node_2.node_id,
        attributes=GraphAttributes(label="участвует", properties=(("role", "seller"),)),
        metadata=GraphMetadata(created_by="test"),
    )
    graph = KnowledgeGraph(nodes=(node_1, node_2), edges=(edge,))

    # Provenance with links
    prov_links = (
        ProvenanceLink(
            graph_node_id=GraphNodeId(value="ent:org-1"),
            source=ProvenanceSource(
                source_type=ProvenanceSourceType.DOCUMENT,
                source_id="doc-001",
                description="OCR-распознавание договора",
            ),
            confidence=0.95,
        ),
        ProvenanceLink(
            graph_node_id=GraphNodeId(value="agr:sale-1"),
            source=ProvenanceSource(
                source_type=ProvenanceSourceType.AGREEMENT,
                source_id="agr-1",
                description="Автоматическое разрешение соглашения",
            ),
            confidence=0.92,
        ),
    )
    provenance = KnowledgeProvenance(
        provenance_id=ProvenanceId(value="prov-001"),
        chain=ProvenanceChain(links=prov_links),
        metadata=ProvenanceMetadata(source_count=2, confidence=0.93),
    )

    # Explanation with steps
    explanation = GraphExplanation(
        explanation_id=ExplanationId(value="exp-001"),
        graph_node_id=GraphNodeId(value="ent:org-1"),
        steps=(
            ExplanationStep(
                step_number=1,
                summary="Извлечение сущности из документа",
                reasons=(
                    ExplanationReason(
                        reason_type=ExplanationReasonType.FACT_MATCH,
                        summary="Факт DOCUMENT_HAS_PARTY",
                        confidence=0.95,
                    ),
                ),
                evidence=(
                    ExplanationEvidence(
                        source_type="ocr", source_id="doc-001",
                        description="Распознанное название компании",
                        confidence=0.94,
                    ),
                ),
            ),
        ),
        overall_confidence=0.94,
        metadata=ExplanationMetadata(created_by="test", knowledge_revision_hint=1),
    )

    # Snapshot
    snapshot = KnowledgeSnapshot(graph=graph, provenance=provenance, explanation=explanation)

    # Revision
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value=str(uuid.uuid4())),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=snapshot,
        metadata=KnowledgeRevisionMetadata(
            created_by="test", reason="Integration test",
            document_count=1, entity_count=1,
        ),
    )


def _make_record(doc_id: str = "test-doc", rev: KnowledgeRevision | None = None) -> KnowledgeRevisionRecord:
    """Create a full KnowledgeRevisionRecord."""
    if rev is None:
        rev = _make_full_revision(doc_id)
    return KnowledgeRevisionRecord(
        revision=rev,
        explanation=rev.snapshot.explanation,
        source_document_id=doc_id,
        processing_job_id=f"job-{doc_id}",
        created_at=datetime.utcnow(),
    )


# ── Tests ─────────────────────────────────────────────────────────

class TestPostgreSQLRepository:
    """Integration tests for PostgreSQLKnowledgeRevisionRepository."""

    def test_save_and_get(self, repo):
        """Save a revision and retrieve it by ID."""
        record = _make_record("test-save-get")
        repo.save(record)

        fetched = repo.get(record.revision.revision_id)
        assert fetched is not None
        assert fetched.revision.revision_id.value == record.revision.revision_id.value
        assert fetched.revision.revision_number.number == 1
        assert fetched.source_document_id == "test-save-get"

    def test_save_and_get_graph(self, repo):
        """Graph nodes and edges survive round-trip."""
        record = _make_record("test-graph")
        repo.save(record)

        fetched = repo.get(record.revision.revision_id)
        rev = fetched.revision
        snap = rev.snapshot
        graph = snap.graph

        assert graph.node_count == 2
        assert graph.edge_count == 1

        # Check node details
        nodes_by_id = {n.node_id.value: n for n in graph.nodes}
        assert "ent:org-1" in nodes_by_id
        assert nodes_by_id["ent:org-1"].node_type == GraphNodeType.ENTITY
        assert nodes_by_id["ent:org-1"].attributes.label == "ООО Продавец"

        # Check edge details
        assert graph.edges[0].edge_type == GraphEdgeType.PARTICIPATES

    def test_save_and_get_provenance(self, repo):
        """Provenance survives round-trip."""
        record = _make_record("test-prov")
        repo.save(record)

        fetched = repo.get(record.revision.revision_id)
        prov = fetched.revision.snapshot.provenance
        assert prov is not None
        assert prov.provenance_id.value == "prov-001"
        links = list(prov.chain.links)
        assert len(links) == 2
        assert links[0].graph_node_id.value == "ent:org-1"
        assert links[0].source.source_type == ProvenanceSourceType.DOCUMENT

    def test_save_and_get_explanation(self, repo):
        """Explanation survives round-trip."""
        record = _make_record("test-exp")
        repo.save(record)

        fetched = repo.get(record.revision.revision_id)
        exp = fetched.revision.snapshot.explanation
        assert exp is not None
        assert exp.explanation_id.value == "exp-001"
        assert exp.step_count == 1
        assert exp.steps[0].summary == "Извлечение сущности из документа"

    def test_idempotent_save_same_content(self, repo):
        """Same content → idempotent (no error)."""
        record = _make_record("test-idempotent")
        repo.save(record)
        repo.save(record)  # second save should not raise
        assert len(repo) == 1

    def test_conflict_different_content(self, repo):
        """Different content with same revision_id → KnowledgeRevisionConflictError."""
        record = _make_record("test-conflict")
        repo.save(record)

        # Create different revision with same ID
        rev2 = KnowledgeRevision(
            revision_id=record.revision.revision_id,
            revision_number=KnowledgeRevisionNumber(number=2),
            snapshot=KnowledgeSnapshot.empty(),
            metadata=KnowledgeRevisionMetadata(reason="Different"),
        )
        record2 = KnowledgeRevisionRecord(
            revision=rev2,
            explanation=rev2.snapshot.explanation,
            source_document_id="different-doc",
        )
        with pytest.raises(KnowledgeRevisionConflictError):
            repo.save(record2)

    def test_get_missing(self, repo):
        """get() returns None for non-existent revision."""
        result = repo.get(KnowledgeRevisionId(value="non-existent"))
        assert result is None

    def test_get_by_document_id(self, repo):
        """get_by_document_id returns all revisions for a document."""
        doc_id = "test-multi"

        r1 = _make_full_revision(doc_id)
        r2 = KnowledgeRevision(
            revision_id=KnowledgeRevisionId(value=str(uuid.uuid4())),
            revision_number=KnowledgeRevisionNumber(number=2),
            snapshot=KnowledgeSnapshot.empty(),
            metadata=KnowledgeRevisionMetadata(reason="Second revision", document_count=1),
        )

        repo.save(_make_record(doc_id, r1))
        repo.save(_make_record(doc_id, r2))

        results = repo.get_by_document_id(doc_id)
        assert len(results) == 2
        assert results[0].revision.revision_number.number == 1
        assert results[1].revision.revision_number.number == 2

    def test_exists(self, repo):
        """exists() returns correct boolean."""
        record = _make_record("test-exists")
        rid = record.revision.revision_id
        assert not repo.exists(rid)
        repo.save(record)
        assert repo.exists(rid)
        assert repo.exists(rid.value)  # string version

    def test_len(self, repo):
        """__len__ returns total count."""
        assert len(repo) == 0
        repo.save(_make_record("doc-a"))
        repo.save(_make_record("doc-b"))
        assert len(repo) == 2

    def test_delete_all(self, repo):
        """delete_all removes all rows."""
        repo.save(_make_record("doc-a"))
        repo.save(_make_record("doc-b"))
        assert len(repo) == 2
        repo.delete_all()
        assert len(repo) == 0

    def test_full_pipeline_roundtrip(self, repo):
        """Simulate a real pipeline: bridge → repository → full read-back."""
        from application.domain_pipeline_bridge import DomainPipelineBridge

        bridge = DomainPipelineBridge()
        result = bridge.process(
            document_id="e2e-pg-test",
            raw_text="ДОГОВОР КУПЛИ-ПРОДАЖИ\nООО Продавец и ООО Покупатель\nСумма: 5 000 000 руб.",
            entities={
                "company": ["ООО Продавец", "ООО Покупатель"],
                "amount": ["5000000"],
                "date": ["15.06.2026"],
            },
            classification="dkp",
            confidence=0.95,
            semantic_type="sale_contract",
            document_role="sale_contract",
        )

        # Build record from pipeline result
        raw_rev = result["revision"]
        snapshot = raw_rev["snapshot"]
        assert snapshot is not None

        rev = KnowledgeRevision(
            revision_id=KnowledgeRevisionId(value=raw_rev["id"]),
            revision_number=KnowledgeRevisionNumber(number=raw_rev["number"]),
            snapshot=snapshot,
            metadata=KnowledgeRevisionMetadata(reason="E2E test", document_count=1),
        )
        explanation = snapshot.explanation
        record = KnowledgeRevisionRecord(
            revision=rev,
            explanation=explanation,
            source_document_id="e2e-pg-test",
            processing_job_id="job-e2e-pg-test",
        )

        # Save to PostgreSQL
        repo.save(record)
        assert len(repo) == 1

        # Read back
        fetched = repo.get(rev.revision_id)
        assert fetched is not None

        # Verify full snapshot integrity
        fsnap = fetched.revision.snapshot
        assert fsnap.graph.node_count > 0, "Graph nodes lost in round-trip"
        assert fsnap.provenance is not None, "Provenance lost in round-trip"
        assert len(list(fsnap.provenance.chain.links)) > 0, "Provenance links lost"
        assert fsnap.explanation is not None, "Explanation lost in round-trip"
        assert fsnap.explanation.step_count > 0, "Explanation steps lost"

        # Verify by document ID
        doc_results = repo.get_by_document_id("e2e-pg-test")
        assert len(doc_results) == 1
        assert doc_results[0].revision.revision_id.value == raw_rev["id"]
        assert doc_results[0].revision.revision_number.number == raw_rev["number"]

        print(f"✅ Full pipeline roundtrip: {fsnap.graph.node_count}n, "
              f"{len(list(fsnap.provenance.chain.links))} prov, "
              f"{fsnap.explanation.step_count} exp")
