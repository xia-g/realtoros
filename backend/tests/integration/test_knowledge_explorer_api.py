"""
Knowledge Explorer — API integration tests.

Tests real HTTP endpoints against a running FastAPI app.
Requires PostgreSQL with knowledge_revisions and projection_store tables.

Run: python3 -m pytest backend/tests/integration/test_knowledge_explorer_api.py -v

These tests verify Knowledge Explorer works over the real Platform
without changing any Platform code.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "services/accounting_binding"))

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
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
from application.knowledge_persistence.integrator import KnowledgeRuntimeIntegrator
from infrastructure.knowledge_persistence.postgresql_knowledge_revision_repository import (
    PostgreSQLKnowledgeRevisionRepository,
)
from infrastructure.knowledge_persistence.postgresql_projection_store import (
    PostgreSQLProjectionStore,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def app():
    """Create FastAPI app and seed test data."""
    application = create_app()

    # Ensure integrator is available in app.state
    dsn = settings.DATABASE_SYNC_URL
    repo = PostgreSQLKnowledgeRevisionRepository(dsn=dsn)
    store = PostgreSQLProjectionStore(dsn=dsn)
    repo.delete_all()
    store.clear()

    integrator = KnowledgeRuntimeIntegrator(
        revision_repository=repo,
        projection_store=store,
    )
    application.state.integrator = integrator

    # Seed test revision data
    node_entity = GraphNode(
        node_id=GraphNodeId(value="ent:test-org"),
        node_type=GraphNodeType.ENTITY,
        domain_id="org-1",
        attributes=GraphAttributes(label="ООО Тест", display_name="Test Org"),
        metadata=GraphMetadata(created_by="test", schema_version=1),
    )
    node_agreement = GraphNode(
        node_id=GraphNodeId(value="agr:test-1"),
        node_type=GraphNodeType.AGREEMENT,
        domain_id="agr-1",
        attributes=GraphAttributes(label="Договор тестовый"),
        metadata=GraphMetadata(created_by="test"),
    )
    edge = GraphEdge(
        edge_id=GraphEdgeId(value="edge-test-1"),
        edge_type=GraphEdgeType.PARTICIPATES,
        source_node=node_entity.node_id,
        target_node=node_agreement.node_id,
        attributes=GraphAttributes(label="участвует"),
        metadata=GraphMetadata(created_by="test"),
    )
    graph = KnowledgeGraph(nodes=(node_entity, node_agreement), edges=(edge,))

    prov_link = ProvenanceLink(
        graph_node_id=GraphNodeId(value="ent:test-org"),
        source=ProvenanceSource(
            source_type=ProvenanceSourceType.DOCUMENT,
            source_id="doc-test-001",
            description="OCR-распознавание",
        ),
        confidence=0.95,
    )
    provenance = KnowledgeProvenance(
        provenance_id=ProvenanceId(value="prov-test-001"),
        chain=ProvenanceChain(links=(prov_link,)),
        metadata=ProvenanceMetadata(source_count=1, confidence=0.95),
    )

    exp_step = ExplanationStep(
        step_number=1,
        summary="Извлечение сущности из документа",
        reasons=(
            ExplanationReason(
                reason_type=ExplanationReasonType.FACT_MATCH,
                summary="Факт DOCUMENT_HAS_PARTY", confidence=0.95,
            ),
        ),
        evidence=(
            ExplanationEvidence(
                source_type="ocr", source_id="doc-test-001",
                description="Распознанная компания", confidence=0.94,
            ),
        ),
    )
    explanation = GraphExplanation(
        explanation_id=ExplanationId(value="exp-test-001"),
        graph_node_id=GraphNodeId(value="ent:test-org"),
        steps=(exp_step,),
        overall_confidence=0.94,
        metadata=ExplanationMetadata(created_by="test"),
    )

    snapshot = KnowledgeSnapshot(graph=graph, provenance=provenance, explanation=explanation)
    revision = KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="explorer-test-revision-001"),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=snapshot,
        metadata=KnowledgeRevisionMetadata(
            created_by="test", reason="Knowledge Explorer test",
            document_count=1, entity_count=1,
        ),
    )
    record = KnowledgeRevisionRecord(
        revision=revision,
        explanation=explanation,
        source_document_id="doc-explorer-test",
        processing_job_id="job-explorer-test",
    )
    repo.save(record)

    yield application

    # Cleanup
    repo.delete_all()
    store.clear()
    application.state.integrator = None


@pytest.fixture
def client(app):
    """Sync HTTP client for FastAPI test app."""
    return TestClient(app)


# ── Tests ─────────────────────────────────────────────────────────


class TestKnowledgeExplorerAPI:
    """Knowledge Explorer API integration tests."""

    def test_list_revisions(self, client):
        """GET /knowledge/revisions returns revision list."""
        resp = client.get("/api/v1/knowledge/revisions")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "revisions" in data
        assert "total" in data
        assert data["total"] >= 1
        rev = data["revisions"][0]
        assert "revision_id" in rev
        assert "revision_number" in rev
        assert "source_document_id" in rev
        assert rev["source_document_id"] == "doc-explorer-test"

    def test_get_revision_detail(self, client):
        """GET /knowledge/revisions/{id} returns revision details."""
        resp = client.get("/api/v1/knowledge/revisions/explorer-test-revision-001")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["revision_id"] == "explorer-test-revision-001"
        assert data["revision_number"] == 1
        assert data["source_document_id"] == "doc-explorer-test"
        assert "snapshot" in data
        assert "graph" in data["snapshot"]
        assert data["snapshot"]["graph"]["node_count"] == 2
        assert "provenance" in data["snapshot"]
        assert "explanation" in data["snapshot"]

    def test_get_revision_graph(self, client):
        """GET /knowledge/revisions/{id}/graph returns graph data."""
        resp = client.get("/api/v1/knowledge/revisions/explorer-test-revision-001/graph")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["node_count"] == 2
        assert data["edge_count"] == 1
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        # Check node details
        node_ids = {n["node_id"] for n in data["nodes"]}
        assert "ent:test-org" in node_ids
        assert "agr:test-1" in node_ids
        # Check edge
        assert data["edges"][0]["source_node"] == "ent:test-org"
        assert data["edges"][0]["target_node"] == "agr:test-1"

    def test_get_revision_provenance(self, client):
        """GET /knowledge/revisions/{id}/provenance returns provenance data."""
        resp = client.get("/api/v1/knowledge/revisions/explorer-test-revision-001/provenance")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["provenance_id"] == "prov-test-001"
        assert data["link_count"] == 1
        assert len(data["links"]) == 1
        assert data["links"][0]["graph_node_id"] == "ent:test-org"
        assert data["links"][0]["source_type"] == "document"

    def test_get_revision_explanation(self, client):
        """GET /knowledge/revisions/{id}/explanation returns explanation data."""
        resp = client.get("/api/v1/knowledge/revisions/explorer-test-revision-001/explanation")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["explanation_id"] == "exp-test-001"
        assert data["step_count"] == 1
        assert len(data["steps"]) == 1
        assert data["overall_confidence"] == 0.94
        assert data["steps"][0]["summary"] == "Извлечение сущности из документа"

    def test_get_revision_not_found(self, client):
        """GET /knowledge/revisions/{id} returns 404 for unknown revision."""
        resp = client.get("/api/v1/knowledge/revisions/non-existent-revision")
        assert resp.status_code == 404

    def test_explorer_works_alongside_existing_knowledge_routes(self, client):
        """Explorer routes don't conflict with existing /knowledge routes."""
        # The existing /knowledge/stats should still work
        resp = client.get("/api/v1/knowledge/stats")
        assert resp.status_code in (200, 422)  # 422 if query param missing
