"""
Knowledge Audit Trail — API integration tests.

Tests the GET /knowledge/audit/{revision_id} endpoint.
Requires PostgreSQL with knowledge_revisions table.

No Platform changes.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "services/accounting_binding"))

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

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
from domain.business_relationship.ke_explanation import GraphExplanation
from domain.business_relationship.ke_explanation_id import ExplanationId
from domain.business_relationship.kg_identifiers import GraphNodeId

from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.integrator import KnowledgeRuntimeIntegrator
from infrastructure.knowledge_persistence.postgresql_knowledge_revision_repository import (
    PostgreSQLKnowledgeRevisionRepository,
)
from infrastructure.knowledge_persistence.postgresql_projection_store import (
    PostgreSQLProjectionStore,
)


DSN = settings.DATABASE_SYNC_URL
DOC = "audit-test-doc"


def _node(nid: str, did: str = "") -> GraphNode:
    return GraphNode(
        node_id=GraphNodeId(value=nid),
        node_type=GraphNodeType.ENTITY,
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


def _link(gid: str, src_id: str = "doc-audit") -> ProvenanceLink:
    return ProvenanceLink(
        graph_node_id=GraphNodeId(value=gid),
        source=ProvenanceSource(
            source_type=ProvenanceSourceType.DOCUMENT,
            source_id=src_id,
            description="Source document",
        ),
    )


def _snapshot(nodes: tuple = (), edges: tuple = (), links: tuple = ()) -> KnowledgeSnapshot:
    return KnowledgeSnapshot(
        graph=KnowledgeGraph(nodes=nodes, edges=edges),
        provenance=KnowledgeProvenance(
            provenance_id=ProvenanceId.generate(),
            chain=ProvenanceChain(links=links),
        ),
        explanation=GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="root"),
        ),
    )


@pytest.fixture
def app():
    app = create_app()
    repo = PostgreSQLKnowledgeRevisionRepository(dsn=DSN)
    store = PostgreSQLProjectionStore(dsn=DSN)
    repo.delete_all()
    store.clear()
    integrator = KnowledgeRuntimeIntegrator(revision_repository=repo, projection_store=store)
    app.state.integrator = integrator

    # Create three revisions for the same document
    snap1 = _snapshot(
        nodes=(_node("n1", "ent-a"),),
        links=(_link("n1"),),
    )
    snap2 = _snapshot(
        nodes=(_node("n1", "ent-a"), _node("n2", "ent-b")),
        edges=(_edge("e1", "n1", "n2"),),
        links=(_link("n1"), _link("n2")),
    )
    snap3 = _snapshot(
        nodes=(_node("n1", "ent-a"), _node("n3", "ent-c")),
        edges=(_edge("e2", "n1", "n3"),),
        links=(_link("n1", "doc-audit"), _link("n3", "doc-other")),
    )

    revs = [
        ("audit-001", 1, DOC, datetime(2026, 1, 1), "Initial", "alice", snap1),
        ("audit-002", 2, DOC, datetime(2026, 2, 1), "Added buyer", "bob", snap2),
        ("audit-003", 3, DOC, datetime(2026, 3, 1), "Updated entities", "alice", snap3),
    ]

    for rid, rnum, doc, dt, reason, by, snap in revs:
        rev = KnowledgeRevision(
            revision_id=KnowledgeRevisionId(value=rid),
            revision_number=KnowledgeRevisionNumber(number=rnum),
            snapshot=snap,
            metadata=KnowledgeRevisionMetadata(
                created_at=dt, created_by=by, reason=reason,
            ),
        )
        repo.save(KnowledgeRevisionRecord(
            revision=rev,
            explanation=rev.snapshot.explanation,
            source_document_id=doc,
        ))

    yield app
    repo.delete_all()
    store.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestAuditAPI:

    def test_audit_returns_revision_metadata(self, client):
        resp = client.get("/api/v1/knowledge/audit/audit-002")
        assert resp.status_code == 200
        data = resp.json()
        rev = data["revision"]
        assert rev["revision_id"] == "audit-002"
        assert rev["revision_number"] == 2
        assert rev["created_by"] == "bob"
        assert rev["reason"] == "Added buyer"
        assert rev["source_document_id"] == DOC

    def test_audit_returns_provenance(self, client):
        resp = client.get("/api/v1/knowledge/audit/audit-002")
        data = resp.json()
        assert len(data["provenance"]) == 2  # n1 + n2
        assert any(p["source_id"] == "doc-audit" for p in data["provenance"])

    def test_audit_runs_consistency_check(self, client):
        resp = client.get("/api/v1/knowledge/audit/audit-003")
        data = resp.json()
        assert data["validation"] is not None
        assert "is_consistent" in data["validation"]
        # audit-003 has no provenance for n3's doc-other
        # but it does have a link, so it should be consistent for structural checks
        assert isinstance(data["validation"]["is_consistent"], bool)

    def test_audit_shows_previous_revision(self, client):
        resp = client.get("/api/v1/knowledge/audit/audit-002")
        data = resp.json()
        assert data["previous_revision"] is not None
        assert data["previous_revision"]["revision_id"] == "audit-001"

    def test_audit_shows_next_revision(self, client):
        resp = client.get("/api/v1/knowledge/audit/audit-002")
        data = resp.json()
        assert data["next_revision"] is not None
        assert data["next_revision"]["revision_id"] == "audit-003"

    def test_audit_first_revision_no_previous(self, client):
        resp = client.get("/api/v1/knowledge/audit/audit-001")
        data = resp.json()
        assert data["previous_revision"] is None
        assert data["next_revision"]["revision_id"] == "audit-002"

    def test_audit_last_revision_no_next(self, client):
        resp = client.get("/api/v1/knowledge/audit/audit-003")
        data = resp.json()
        assert data["next_revision"] is None
        assert data["previous_revision"]["revision_id"] == "audit-002"

    def test_audit_total_count(self, client):
        resp = client.get("/api/v1/knowledge/audit/audit-001")
        data = resp.json()
        assert data["total_revisions_for_document"] == 3

    def test_audit_nonexistent_returns_404(self, client):
        resp = client.get("/api/v1/knowledge/audit/nonexistent")
        assert resp.status_code == 404

    def test_audit_deterministic(self, client):
        r1 = client.get("/api/v1/knowledge/audit/audit-002")
        r2 = client.get("/api/v1/knowledge/audit/audit-002")
        assert r1.json() == r2.json()
