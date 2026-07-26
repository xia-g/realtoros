"""
Knowledge Search API — integration tests.

Tests the GET /knowledge/search endpoint.
Requires PostgreSQL with knowledge_revisions table.

Run: python3 -m pytest backend/tests/integration/test_knowledge_search_api.py -v

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
from domain.business_relationship.kg_enums import GraphNodeType
from domain.business_relationship.kg_identifiers import GraphNodeId
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


def _snapshot() -> KnowledgeSnapshot:
    return KnowledgeSnapshot(
        graph=KnowledgeGraph(),
        provenance=KnowledgeProvenance(provenance_id=ProvenanceId.generate()),
        explanation=GraphExplanation(
            explanation_id=ExplanationId.generate(),
            graph_node_id=GraphNodeId(value="root"),
        ),
    )


def _make_rev(rev_id: str, number: int, doc_id: str,
              created_at: datetime, reason: str = "",
              created_by: str = "test") -> KnowledgeRevision:
    return KnowledgeRevision(
        revision_id=KnowledgeRevisionId(value=rev_id),
        revision_number=KnowledgeRevisionNumber(number=number),
        snapshot=_snapshot(),
        metadata=KnowledgeRevisionMetadata(
            created_at=created_at,
            created_by=created_by,
            reason=reason,
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

    doc_a = "search-doc-a"
    doc_b = "search-doc-b"

    revisions = [
        _make_rev("search-001", 1, doc_a, datetime(2026, 1, 15), "Initial creation", "alice"),
        _make_rev("search-002", 2, doc_a, datetime(2026, 2, 1), "Added buyer entity", "bob"),
        _make_rev("search-003", 3, doc_a, datetime(2026, 3, 10), "Corrected cadastral", "alice"),
        _make_rev("search-004", 4, doc_b, datetime(2026, 4, 5), "Agreement signed", "bob"),
        _make_rev("search-005", 5, doc_b, datetime(2026, 5, 20), "Final approval", "charlie"),
    ]

    for i, r in enumerate(revisions):
        doc_id = doc_a if i < 3 else doc_b
        repo.save(KnowledgeRevisionRecord(
            revision=r,
            explanation=r.snapshot.explanation,
            source_document_id=doc_id,
        ))

    yield app
    repo.delete_all()
    store.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestSearchAPI:

    def test_search_empty_result(self, client):
        """No matches → empty items, cursor null."""
        resp = client.get("/api/v1/knowledge/search?source_document_id=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["next_cursor"] is None
        assert data["total_matches"] == 0

    def test_search_all_revisions(self, client):
        """No filters → returns all, in created_at DESC + revision_id DESC order."""
        resp = client.get("/api/v1/knowledge/search")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        # DESC order by created_at
        ids = [i["revision_id"] for i in data["items"]]
        assert ids == ["search-005", "search-004", "search-003", "search-002", "search-001"]

    def test_search_by_document(self, client):
        """Filter by source_document_id."""
        resp = client.get("/api/v1/knowledge/search?source_document_id=search-doc-b")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["source_document_id"] == "search-doc-b"

    def test_search_by_reason(self, client):
        """Filter by reason ILIKE."""
        resp = client.get("/api/v1/knowledge/search?reason_contains=agreement")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1
        assert any("agreement" in i["reason"].lower() for i in data["items"])

    def test_search_by_created_by(self, client):
        """Filter by exact created_by."""
        resp = client.get("/api/v1/knowledge/search?created_by=alice")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["created_by"] == "alice"

    def test_search_date_range(self, client):
        """Filter by created_after and created_before."""
        resp = client.get(
            "/api/v1/knowledge/search"
            "?created_after=2026-02-01T00:00:00"
            "&created_before=2026-04-01T00:00:00"
        )
        assert resp.status_code == 200
        data = resp.json()
        # search-002 (Feb 1), search-003 (Mar 10)
        ids = [i["revision_id"] for i in data["items"]]
        assert "search-002" in ids
        assert "search-003" in ids
        assert "search-001" not in ids  # Jan 15 — before range

    def test_search_pagination(self, client):
        """Cursor-based pagination works."""
        r1 = client.get("/api/v1/knowledge/search?limit=2")
        assert r1.status_code == 200
        d1 = r1.json()
        assert len(d1["items"]) == 2
        assert d1["next_cursor"] is not None
        assert d1["items"][0]["revision_id"] == "search-005"
        assert d1["items"][1]["revision_id"] == "search-004"

        # Second page
        r2 = client.get(f"/api/v1/knowledge/search?limit=2&cursor={d1['next_cursor']}")
        assert r2.status_code == 200
        d2 = r2.json()
        assert len(d2["items"]) == 2
        assert d2["items"][0]["revision_id"] == "search-003"
        assert d2["items"][1]["revision_id"] == "search-002"
        assert d2["next_cursor"] is not None

        # Third page
        r3 = client.get(f"/api/v1/knowledge/search?limit=2&cursor={d2['next_cursor']}")
        assert r3.status_code == 200
        d3 = r3.json()
        assert len(d3["items"]) == 1
        assert d3["items"][0]["revision_id"] == "search-001"
        assert d3["next_cursor"] is None

    def test_search_revision_number_range(self, client):
        """Filter by revision_number range."""
        resp = client.get("/api/v1/knowledge/search?revision_number_min=3&revision_number_max=4")
        assert resp.status_code == 200
        data = resp.json()
        ids = {i["revision_id"] for i in data["items"]}
        assert "search-003" in ids
        assert "search-004" in ids
        assert "search-001" not in ids

    def test_search_deterministic(self, client):
        """Same query → same result."""
        r1 = client.get("/api/v1/knowledge/search?limit=3")
        r2 = client.get("/api/v1/knowledge/search?limit=3")
        assert r1.json() == r2.json()

    def test_search_sort_asc(self, client):
        """ASC sort works."""
        resp = client.get("/api/v1/knowledge/search?sort_field=created_at&sort_direction=ASC&limit=3")
        data = resp.json()
        ids = [i["revision_id"] for i in data["items"]]
        assert ids == ["search-001", "search-002", "search-003"]  # oldest first

    def test_search_combined_filters(self, client):
        """Multiple AND filters work together."""
        resp = client.get(
            "/api/v1/knowledge/search"
            "?created_by=alice"
            "&source_document_id=search-doc-a"
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["created_by"] == "alice"
            assert item["source_document_id"] == "search-doc-a"
