"""
Knowledge Consistency Check — API integration tests.

Tests the GET /knowledge/consistency/{revision_id} endpoint.
Also tests GET /knowledge/consistency/latest.

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


def _node(nid: str, did: str = "", ntype: GraphNodeType = GraphNodeType.ENTITY) -> GraphNode:
    return GraphNode(
        node_id=GraphNodeId(value=nid),
        node_type=ntype,
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
        attributes=GraphAttributes(),
        metadata=GraphMetadata(created_by="test"),
    )


def _link(gid: str) -> ProvenanceLink:
    return ProvenanceLink(
        graph_node_id=GraphNodeId(value=gid),
        source=ProvenanceSource(
            source_type=ProvenanceSourceType.DOCUMENT,
            source_id="doc-cons",
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

    # Valid revision
    a = _node("n1", "ent-a")
    b = _node("n2", "ent-b")
    valid_snap = _snapshot(
        nodes=(a, b),
        edges=(_edge("e1", "n1", "n2"),),
        links=(_link("n1"), _link("n2")),
    )
    valid_rev = KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="cons-valid"),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=valid_snap,
        metadata=KnowledgeRevisionMetadata(
            created_at=datetime(2026, 1, 1), created_by="test",
        ),
    )
    repo.save(KnowledgeRevisionRecord(
        revision=valid_rev,
        explanation=valid_rev.snapshot.explanation,
        source_document_id="doc-cons",
    ))

    # Revision with broken edge
    c = _node("n3", "ent-c")
    broken_snap = _snapshot(
        nodes=(c,),
        edges=(_edge("e2", "n3", "missing-node"),),
        links=(_link("n3"),),
    )
    broken_rev = KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="cons-broken"),
        revision_number=KnowledgeRevisionNumber(number=2),
        snapshot=broken_snap,
        metadata=KnowledgeRevisionMetadata(
            created_at=datetime(2026, 2, 1), created_by="test",
        ),
    )
    repo.save(KnowledgeRevisionRecord(
        revision=broken_rev,
        explanation=broken_rev.snapshot.explanation,
        source_document_id="doc-cons",
    ))

    yield app
    repo.delete_all()
    store.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestConsistencyAPI:

    def test_valid_revision_returns_consistent(self, client):
        resp = client.get("/api/v1/knowledge/consistency/cons-valid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_consistent"] is True
        assert data["violations"] == []
        assert data["errors"] == 0

    def test_broken_revision_detects_errors(self, client):
        resp = client.get("/api/v1/knowledge/consistency/cons-broken")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_consistent"] is False
        assert any(v["type"] == "broken_edge" for v in data["violations"])
        assert data["errors"] >= 1

    def test_nonexistent_revision_returns_404(self, client):
        resp = client.get("/api/v1/knowledge/consistency/nonexistent")
        assert resp.status_code == 404

    def test_latest_endpoint(self, client):
        resp = client.get("/api/v1/knowledge/consistency/latest")
        assert resp.status_code == 200
        data = resp.json()
        # Latest is cons-broken (created Feb)
        assert data["revision_id"] == "cons-broken"
        assert data["is_consistent"] is False

    def test_checked_counts(self, client):
        resp = client.get("/api/v1/knowledge/consistency/cons-valid")
        data = resp.json()
        assert data["checked_nodes"] == 2
        assert data["checked_edges"] == 1
