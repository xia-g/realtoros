"""
Knowledge Graph Traversal — API integration tests.

Tests the GET /knowledge/traversal endpoint.
Requires PostgreSQL with knowledge_revisions and projection_store.

Run: python3 -m pytest backend/tests/integration/test_knowledge_traversal_api.py -v

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


def _node(domain_id: str, ntype: GraphNodeType = GraphNodeType.ENTITY,
           label: str = "", node_id_str: str = "") -> GraphNode:
    return GraphNode(
        node_id=GraphNodeId(value=node_id_str or f"node-{domain_id}"),
        node_type=ntype,
        domain_id=domain_id,
        attributes=GraphAttributes(label=label or domain_id, display_name=label or domain_id),
        metadata=GraphMetadata(created_by="test"),
    )


def _edge(src_id: str, tgt_id: str, etype: GraphEdgeType = GraphEdgeType.REFERENCES) -> GraphEdge:
    return GraphEdge(
        edge_id=GraphEdgeId(value=f"edge-{src_id}-{tgt_id}"),
        edge_type=etype,
        source_node=GraphNodeId(value=src_id),
        target_node=GraphNodeId(value=tgt_id),
        attributes=GraphAttributes(),
        metadata=GraphMetadata(created_by="test"),
    )


def _snapshot(nodes: tuple = (), edges: tuple = ()) -> KnowledgeSnapshot:
    return KnowledgeSnapshot(
        graph=KnowledgeGraph(nodes=nodes, edges=edges),
        provenance=KnowledgeProvenance(provenance_id=ProvenanceId.generate()),
        explanation=GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="root"),
        ),
    )


def _make_rev(rev_id: str, doc_id: str, created_at: datetime,
              snapshot: KnowledgeSnapshot, reason: str = "") -> KnowledgeRevision:
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value=rev_id),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=snapshot,
        metadata=KnowledgeRevisionMetadata(
            created_at=created_at,
            created_by="test",
            reason=reason or "traversal-test",
            document_count=1,
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

    # Build a graph:
    #   [seller] --participates--> [agreement-1]
    #   [buyer]  --participates--> [agreement-1]
    #   [agreement-1] --references--> [doc-001]
    nodes = (
        _node("ent-seller", GraphNodeType.ENTITY, "Seller Corp", "node-seller"),
        _node("ent-buyer", GraphNodeType.ENTITY, "Buyer LLC", "node-buyer"),
        _node("agr-001", GraphNodeType.AGREEMENT, "Contract #1", "node-agr-001"),
        _node("doc-001", GraphNodeType.DOCUMENT, "Purchase Agreement", "node-doc-001"),
    )
    edges = (
        _edge("node-seller", "node-agr-001", GraphEdgeType.PARTICIPATES),
        _edge("node-buyer", "node-agr-001", GraphEdgeType.PARTICIPATES),
        _edge("node-agr-001", "node-doc-001", GraphEdgeType.REFERENCES),
    )

    snap = _snapshot(nodes=nodes, edges=edges)
    rev = _make_rev("trav-rev-001", "trav-doc", datetime(2026, 1, 15), snap)

    repo.save(KnowledgeRevisionRecord(
        revision=rev,
        explanation=rev.snapshot.explanation,
        source_document_id="trav-doc",
    ))

    yield app
    repo.delete_all()
    store.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestTraversalAPI:

    def test_traversal_from_entity(self, client):
        """Starting from seller → finds connected nodes (buyer, agreement)."""
        resp = client.get("/api/v1/knowledge/traversal?node_type=entity&domain_id=ent-seller")
        assert resp.status_code == 200
        data = resp.json()
        assert data["root"] is not None
        assert data["root"]["domain_id"] == "ent-seller"
        # Should find: agreement-1, then through agreement: buyer
        node_domains = {n["domain_id"] for n in data["nodes"]}
        assert "agr-001" in node_domains

    def test_traversal_from_entity_no_relations(self, client):
        """An entity with only self → no relations (but root exists)."""
        # doc-001 has incoming edge, not outgoing
        resp = client.get("/api/v1/knowledge/traversal?node_type=document&domain_id=doc-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["root"] is not None
        assert data["root"]["domain_id"] == "doc-001"

    def test_traversal_unknown_entity(self, client):
        """Non-existent entity returns empty result."""
        resp = client.get("/api/v1/knowledge/traversal?node_type=entity&domain_id=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["root"] is None
        assert data["nodes"] == []

    def test_traversal_from_revision(self, client):
        """Starting from revision returns all entities + their relationships."""
        resp = client.get("/api/v1/knowledge/traversal?revision_id=trav-rev-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["root"] is not None
        assert len(data["nodes"]) >= 1  # neighbours
        assert len(data["edges"]) >= 1  # relationships

    def test_traversal_revision_not_found(self, client):
        """Unknown revision returns 404."""
        resp = client.get("/api/v1/knowledge/traversal?revision_id=nonexistent")
        assert resp.status_code == 404

    def test_traversal_missing_params(self, client):
        """No params → 400."""
        resp = client.get("/api/v1/knowledge/traversal")
        assert resp.status_code == 400

    def test_traversal_deterministic(self, client):
        """Same input → same output."""
        r1 = client.get("/api/v1/knowledge/traversal?node_type=entity&domain_id=ent-seller")
        r2 = client.get("/api/v1/knowledge/traversal?node_type=entity&domain_id=ent-seller")
        assert r1.json() == r2.json()

    def test_traversal_connected_entities(self, client):
        """Seller and buyer are both connected to the same agreement."""
        r1 = client.get("/api/v1/knowledge/traversal?node_type=entity&domain_id=ent-seller")
        r2 = client.get("/api/v1/knowledge/traversal?node_type=entity&domain_id=ent-buyer")
        d1 = r1.json()
        d2 = r2.json()
        # Both should find agr-001
        d1_agreements = {n["domain_id"] for n in d1["nodes"]}
        d2_agreements = {n["domain_id"] for n in d2["nodes"]}
        assert "agr-001" in d1_agreements
        assert "agr-001" in d2_agreements
