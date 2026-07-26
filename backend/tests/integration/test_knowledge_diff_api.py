"""
Knowledge Diff Explorer — API integration tests.

Tests the GET /knowledge/revisions/{left}/diff/{right} endpoint.
Requires PostgreSQL with knowledge_revisions table.

Run: python3 -m pytest backend/tests/integration/test_knowledge_diff_api.py -v

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
from domain.business_relationship.ke_explanation_step import ExplanationStep
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
           label: str = "", tags: tuple = ()) -> GraphNode:
    return GraphNode(
        node_id=GraphNodeId(value=f"node-{domain_id}"),
        node_type=ntype,
        domain_id=domain_id,
        attributes=GraphAttributes(label=label or domain_id, display_name=label or domain_id, tags=tags),
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


def _link(graph_node_id: str, source_id: str, source_type: str = "document") -> ProvenanceLink:
    return ProvenanceLink(
        graph_node_id=GraphNodeId(value=graph_node_id),
        source=ProvenanceSource(
            source_type=ProvenanceSourceType(source_type),
            source_id=source_id or f"src-{graph_node_id}",
        ),
    )


def _step(sn: int, summary: str = "") -> ExplanationStep:
    return ExplanationStep(step_number=sn, summary=summary or f"Step {sn}")


def _make_revision(rev_id: str, doc_id: str, created_at: datetime,
                   nodes: tuple = (), edges: tuple = (),
                   links: tuple = (), steps: tuple = (),
                   reason: str = "") -> KnowledgeRevision:
    graph = KnowledgeGraph(nodes=nodes, edges=edges)
    prov = KnowledgeProvenance(
        provenance_id=ProvenanceId.generate(),
        chain=ProvenanceChain(links=links),
    )
    expl = GraphExplanation(
        explanation_id=ExplanationId.generate(),
        graph_node_id=GraphNodeId(value="root"),
    )
    if steps:
        object.__setattr__(expl, "steps", steps)
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value=rev_id),
        revision_number=KnowledgeRevisionNumber(number=1),
        snapshot=KnowledgeSnapshot(graph=graph, provenance=prov, explanation=expl),
        metadata=KnowledgeRevisionMetadata(
            created_at=created_at,
            created_by="test",
            reason=reason or "diff-test",
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

    doc = "diff-test-doc"

    # ── Left revision: 3 nodes, 2 edges, 2 provenance links, 2 steps ──
    left_nodes = (
        _node("ent-seller", GraphNodeType.ENTITY, "Seller"),
        _node("ent-buyer", GraphNodeType.ENTITY, "Buyer"),
        _node("agr-1", GraphNodeType.AGREEMENT, "Agreement #1"),
    )
    left_edges = (
        _edge(left_nodes[0].node_id.value, left_nodes[1].node_id.value, GraphEdgeType.PARTICIPATES),
        _edge(left_nodes[2].node_id.value, left_nodes[0].node_id.value, GraphEdgeType.REFERENCES),
    )
    left_links = (
        _link(left_nodes[0].node_id.value, "doc-001"),
        _link(left_nodes[2].node_id.value, "doc-001"),
    )
    left_steps = (_step(1, "Extract entities"), _step(2, "Build graph"))
    left_rev = _make_revision("diff-left", doc, datetime(2026, 1, 1),
                               nodes=left_nodes, edges=left_edges,
                               links=left_links, steps=left_steps)
    repo.save(KnowledgeRevisionRecord(
        revision=left_rev,
        explanation=left_rev.snapshot.explanation,
        source_document_id=doc,
    ))

    # ── Right revision: 2 nodes (seller removed→renamed? no, buyer kept, entity-c kept),
    #    1 edge (participates removed), 1 new link, 3 steps ──
    right_nodes = (
        _node("ent-buyer", GraphNodeType.ENTITY, "Buyer (updated)"),
        _node("ent-c", GraphNodeType.ENTITY, "New Entity C"),
    )
    right_edges = (
        _edge(right_nodes[0].node_id.value, right_nodes[1].node_id.value, GraphEdgeType.RELATED_TO),
    )
    right_links = (
        _link(right_nodes[0].node_id.value, "doc-001"),
        _link(right_nodes[1].node_id.value, "doc-002"),
    )
    right_steps = (_step(1, "Extract entities"), _step(3, "Validate agreement"))
    right_rev = _make_revision("diff-right", doc, datetime(2026, 2, 1),
                                nodes=right_nodes, edges=right_edges,
                                links=right_links, steps=right_steps,
                                reason="Updated after review")
    repo.save(KnowledgeRevisionRecord(
        revision=right_rev,
        explanation=right_rev.snapshot.explanation,
        source_document_id=doc,
    ))

    yield app
    repo.delete_all()
    store.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestDiffAPI:

    def test_diff_returns_200(self, client):
        resp = client.get("/api/v1/knowledge/revisions/diff-left/diff/diff-right")
        assert resp.status_code == 200

    def test_diff_nodes_added_removed_updated(self, client):
        resp = client.get("/api/v1/knowledge/revisions/diff-left/diff/diff-right")
        data = resp.json()
        # Left: ent-seller, ent-buyer, agr-1
        # Right: ent-buyer (updated), ent-c (new)
        nodes = data["nodes"]
        removed_ids = {n["domain_id"] for n in nodes["removed"]}
        added_ids = {n["domain_id"] for n in nodes["added"]}
        updated_ids = {n["domain_id"] for n in nodes["updated"]}
        assert "ent-seller" in removed_ids
        assert "agr-1" in removed_ids
        assert "ent-c" in added_ids
        assert "ent-buyer" in updated_ids

    def test_diff_edges_added_removed(self, client):
        resp = client.get("/api/v1/knowledge/revisions/diff-left/diff/diff-right")
        data = resp.json()["edges"]
        # participates (left) removed, related_to (right) added
        assert len(data["removed"]) >= 1
        assert len(data["added"]) >= 1

    def test_diff_provenance(self, client):
        resp = client.get("/api/v1/knowledge/revisions/diff-left/diff/diff-right")
        data = resp.json()["provenance"]
        # Both sides have doc-001 provenance (different nodes, same source).
        # Right adds doc-002 for the new entity.
        assert len(data["added"]) >= 1  # doc-002 added

    def test_diff_explanation(self, client):
        resp = client.get("/api/v1/knowledge/revisions/diff-left/diff/diff-right")
        data = resp.json()["explanation"]
        # step 2 removed, step 3 added, step 1 unchanged
        removed_nums = {s["step_number"] for s in data["removed"]}
        added_nums = {s["step_number"] for s in data["added"]}
        assert 2 in removed_nums
        assert 3 in added_nums

    def test_diff_empty_when_same_revision(self, client):
        resp = client.get("/api/v1/knowledge/revisions/diff-left/diff/diff-left")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["nodes_added"] == 0
        assert data["summary"]["nodes_removed"] == 0
        assert data["summary"]["nodes_updated"] == 0
        assert data["summary"]["edges_added"] == 0
        assert data["summary"]["edges_removed"] == 0
        assert data["summary"]["explanation_added"] == 0
        assert data["summary"]["explanation_removed"] == 0

    def test_diff_404_left_missing(self, client):
        resp = client.get("/api/v1/knowledge/revisions/non-existent/diff/diff-right")
        assert resp.status_code == 404

    def test_diff_404_right_missing(self, client):
        resp = client.get("/api/v1/knowledge/revisions/diff-left/diff/non-existent")
        assert resp.status_code == 404

    def test_diff_summary_counts(self, client):
        resp = client.get("/api/v1/knowledge/revisions/diff-left/diff/diff-right")
        summary = resp.json()["summary"]
        assert summary["nodes_added"] >= 1
        assert summary["nodes_removed"] >= 2
        assert summary["nodes_updated"] >= 1
        assert summary["edges_added"] >= 1
        assert summary["edges_removed"] >= 1
