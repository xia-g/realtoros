"""
Knowledge Trust State — API integration tests.

Tests GET /knowledge/trust/{revision_id} and /knowledge/trust/latest.
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
from domain.business_relationship.kg_attributes import GraphAttributes
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


def _node(nid: str, did: str = "") -> GraphNode:
    return GraphNode(node_id=GraphNodeId(value=nid), node_type=GraphNodeType.ENTITY,
                     domain_id=did or nid, attributes=GraphAttributes(label=did or nid))


def _edge(eid: str, src: str, tgt: str) -> GraphEdge:
    return GraphEdge(edge_id=GraphEdgeId(value=eid), edge_type=GraphEdgeType.REFERENCES,
                     source_node=GraphNodeId(value=src), target_node=GraphNodeId(value=tgt))


def _link(gid: str) -> ProvenanceLink:
    return ProvenanceLink(graph_node_id=GraphNodeId(value=gid),
                          source=ProvenanceSource(source_type=ProvenanceSourceType.DOCUMENT, source_id="doc"))


def _snap(nodes=(), edges=(), links=()):
    nodes_t = tuple(nodes) if not isinstance(nodes, tuple) else nodes
    edges_t = tuple(edges) if not isinstance(edges, tuple) else edges
    links_t = tuple(links) if not isinstance(links, tuple) else links
    return KnowledgeSnapshot(
        graph=KnowledgeGraph(nodes=nodes_t, edges=edges_t),
        provenance=KnowledgeProvenance(provenance_id=ProvenanceId.generate(),
                                        chain=ProvenanceChain(links=links)),
        explanation=GraphExplanation(explanation_id=ExplanationId.generate(),
                                      graph_node_id=GraphNodeId(value="root")),
    )


@pytest.fixture
def app():
    app = create_app()
    repo = PostgreSQLKnowledgeRevisionRepository(dsn=DSN)
    store = PostgreSQLProjectionStore(dsn=DSN)
    repo.delete_all()
    store.clear()
    app.state.integrator = KnowledgeRuntimeIntegrator(revision_repository=repo, projection_store=store)

    # Valid revision
    a, b = _node("n1", "ent-a"), _node("n2", "ent-b")
    valid = KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="trust-valid"),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=_snap(nodes=(a, b), edges=(_edge("e1", "n1", "n2"),), links=(_link("n1"), _link("n2"))),
        metadata=KnowledgeRevisionMetadata(created_at=datetime(2026, 1, 1), created_by="test"),
    )
    repo.save(KnowledgeRevisionRecord(revision=valid, explanation=valid.snapshot.explanation, source_document_id="doc"))

    # Broken revision
    c = _node("n3", "ent-c")
    broken = KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value="trust-broken"),
        revision_number=KnowledgeRevisionNumber(number=2),
        snapshot=_snap(nodes=(c,), edges=(_edge("e2", "n3", "missing"),), links=(_link("n3"),)),
        metadata=KnowledgeRevisionMetadata(created_at=datetime(2026, 2, 1), created_by="test"),
    )
    repo.save(KnowledgeRevisionRecord(revision=broken, explanation=broken.snapshot.explanation, source_document_id="doc"))

    yield app
    repo.delete_all()
    store.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestTrustAPI:

    def test_valid_revision(self, client):
        r = client.get("/api/v1/knowledge/trust/trust-valid")
        assert r.status_code == 200
        assert r.json()["trust"]["status"] == "VALID"

    def test_broken_revision(self, client):
        r = client.get("/api/v1/knowledge/trust/trust-broken")
        assert r.status_code == 200
        assert r.json()["trust"]["status"] == "INVALID"

    def test_nonexistent(self, client):
        r = client.get("/api/v1/knowledge/trust/nonexistent")
        assert r.status_code == 404

    def test_latest(self, client):
        r = client.get("/api/v1/knowledge/trust/latest")
        assert r.status_code == 200
        assert r.json()["trust"]["status"] == "INVALID"  # broken is latest

    def test_deterministic(self, client):
        r1 = client.get("/api/v1/knowledge/trust/trust-valid")
        r2 = client.get("/api/v1/knowledge/trust/trust-valid")
        assert r1.json()["trust"]["status"] == r2.json()["trust"]["status"]
