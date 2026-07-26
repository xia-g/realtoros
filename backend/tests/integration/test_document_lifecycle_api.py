"""
Epic 1 / Stream 1 — Document Intake & Lifecycle API tests.

Tests upload, lifecycle transitions, status, error states, mark-ready.
"""
from __future__ import annotations

import sys, os, io, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import pytest
from fastapi.testclient import TestClient
from fastapi import UploadFile

from backend.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _upload_doc(client) -> str:
    """Helper: upload a document and return its ID."""
    content = b"test content for lifecycle"
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", content, "application/pdf")},
        data={"organization_id": "org-test"},
    )
    assert resp.status_code == 200
    return resp.json()["document_id"]


def _walk_to(client, doc_id: str, target: str):
    """Helper: walk document through the lifecycle to a target state."""
    lifecycle = [
        ("VALIDATED", "validation"),
        ("ACCEPTED", "accepted"),
        ("PROCESSING", "ocr"),
        ("ANALYZED", "analysis"),
        ("READY", "ready"),
        ("ROUTED", "routing"),
        ("ARCHIVED", "archived"),
    ]
    for state, stage in lifecycle:
        resp = client.post(
            f"/api/v1/documents/{doc_id}/transition",
            json={"target_status": state, "pipeline_stage": stage},
        )
        if state == target:
            return resp
        if resp.status_code != 200:
            return resp
    return resp


def _walk_through(client, doc_id: str, states: list[tuple[str, str]]):
    """Helper: walk through specific states."""
    for state, stage in states:
        resp = client.post(
            f"/api/v1/documents/{doc_id}/transition",
            json={"target_status": state, "pipeline_stage": stage},
        )
        if resp.status_code != 200:
            return resp
    return resp


class TestDocumentLifecycle:

    DOC_ID = None

    def test_1_upload_pdf(self, client):
        """Upload a PDF → status UPLOADED."""
        content = b"%PDF-1.4 fake pdf content for testing"
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", content, "application/pdf")},
            data={"organization_id": "org-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "UPLOADED"
        assert data["pipeline_stage"] == "intake"
        assert data["mime_type"] == "application/pdf"
        assert data["size_bytes"] == len(content)
        assert data["original_filename"] == "test.pdf"
        assert len(data["checksum"]) == 64  # sha256
        TestDocumentLifecycle.DOC_ID = data["document_id"]

    def test_2_get_document(self, client):
        """GET /documents/{id} returns document details."""
        assert TestDocumentLifecycle.DOC_ID
        resp = client.get(f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == TestDocumentLifecycle.DOC_ID
        assert data["status"] == "UPLOADED"

    def test_3_get_status(self, client):
        """GET /documents/{id}/status returns status + allowed transitions."""
        resp = client.get(f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "UPLOADED"
        assert "VALIDATED" in data["allowed_transitions"]
        assert "REJECTED" in data["allowed_transitions"]

    def test_4_transition_validated(self, client):
        """UPLOADED → VALIDATED."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "VALIDATED", "pipeline_stage": "validation"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "VALIDATED"

    def test_5_transition_accepted(self, client):
        """VALIDATED → ACCEPTED."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "ACCEPTED", "pipeline_stage": "accepted"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACCEPTED"

    def test_6_transition_processing(self, client):
        """ACCEPTED → PROCESSING."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "PROCESSING", "pipeline_stage": "ocr"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "PROCESSING"

    def test_7_transition_analyzed(self, client):
        """PROCESSING → ANALYZED."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "ANALYZED", "pipeline_stage": "analysis"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ANALYZED"

    def test_8_transition_ready(self, client):
        """ANALYZED → READY."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "READY", "pipeline_stage": "ready"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "READY"
        # Profile should be settable
        assert "profile" in data

    def test_9_transition_routed(self, client):
        """READY → ROUTED."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "ROUTED", "pipeline_stage": "routing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ROUTED"

    def test_10_transition_archived(self, client):
        """ROUTED → ARCHIVED."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "ARCHIVED", "pipeline_stage": "archived"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ARCHIVED"

    def test_11_terminal_no_transitions(self, client):
        """ARCHIVED is terminal — no more transitions."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "PROCESSING"},
        )
        assert resp.status_code == 400
        assert "terminal" in resp.json()["detail"].lower()

    def test_12_invalid_transition(self, client):
        """ARCHIVED → PROCESSING is invalid."""
        resp = client.post(
            f"/api/v1/documents/{TestDocumentLifecycle.DOC_ID}/transition",
            json={"target_status": "PROCESSING"},
        )
        assert resp.status_code == 400

    def test_13_document_not_found(self, client):
        """Non-existent document returns 404."""
        resp = client.get("/api/v1/documents/non-existent-id")
        assert resp.status_code == 404

    def test_14_upload_empty_file(self, client):
        """Empty file upload returns 400."""
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_15_reject_flow(self, client):
        """UPLOADED → REJECTED is valid."""
        content = b"some content"
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("reject.pdf", content, "application/pdf")},
        )
        doc_id = resp.json()["document_id"]
        resp = client.post(
            f"/api/v1/documents/{doc_id}/transition",
            json={"target_status": "REJECTED"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "REJECTED"

    def test_16_full_lifecycle_upload_only(self, client):
        """Upload only — check that upload creates a valid document."""
        content = b"lifecycle test content"
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("lifecycle.pdf", content, "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "UPLOADED"
        assert data["original_filename"] == "lifecycle.pdf"


class TestDocumentMarkReady:
    """Tests for POST /documents/{id}/mark-ready endpoint."""

    def test_mark_ready_from_analyzed(self, client):
        """Upload → walk to ANALYZED → /mark-ready → 200, status=READY."""
        doc_id = _upload_doc(client)

        # Walk to ANALYZED
        resp = _walk_through(client, doc_id, [
            ("VALIDATED", "validation"),
            ("ACCEPTED", "accepted"),
            ("PROCESSING", "ocr"),
            ("ANALYZED", "analysis"),
        ])
        assert resp.status_code == 200
        assert resp.json()["status"] == "ANALYZED"

        # Mark ready
        resp = client.post(f"/api/v1/documents/{doc_id}/mark-ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "READY"

    def test_mark_ready_idempotent(self, client):
        """/mark-ready второй раз → 400."""
        doc_id = _upload_doc(client)
        resp = _walk_through(client, doc_id, [
            ("VALIDATED", "validation"),
            ("ACCEPTED", "accepted"),
            ("PROCESSING", "ocr"),
            ("ANALYZED", "analysis"),
        ])
        assert resp.status_code == 200

        # First call — success
        resp = client.post(f"/api/v1/documents/{doc_id}/mark-ready")
        assert resp.status_code == 200

        # Second call — 409 Conflict (idempotency guard)
        resp = client.post(f"/api/v1/documents/{doc_id}/mark-ready")
        assert resp.status_code == 409

    def test_mark_ready_from_wrong_state(self, client):
        """Upload → /mark-ready (from UPLOADED) → 422."""
        doc_id = _upload_doc(client)
        resp = client.post(f"/api/v1/documents/{doc_id}/mark-ready")
        assert resp.status_code == 422
        assert "Cannot transition" in resp.json()["detail"]

    def test_mark_ready_event_published(self, client):
        """В ответе есть event_id и event_type."""
        doc_id = _upload_doc(client)
        resp = _walk_through(client, doc_id, [
            ("VALIDATED", "validation"),
            ("ACCEPTED", "accepted"),
            ("PROCESSING", "ocr"),
            ("ANALYZED", "analysis"),
        ])
        assert resp.status_code == 200

        resp = client.post(f"/api/v1/documents/{doc_id}/mark-ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_id"] is not None
        assert data["event_type"] == "document.ready"

    def test_mark_ready_not_found(self, client):
        """Несуществующий ID → 404."""
        resp = client.post("/api/v1/documents/non-existent-id/mark-ready")
        assert resp.status_code == 404

    def test_mark_ready_from_needs_review(self, client):
        """NEEDS_REVIEW → /mark-ready → 200 (разрешено в VALID_TRANSITIONS)."""
        doc_id = _upload_doc(client)
        # Walk to PROCESSING then NEEDS_REVIEW (PROCESSING → NEEDS_REVIEW is valid)
        resp = _walk_through(client, doc_id, [
            ("VALIDATED", "validation"),
            ("ACCEPTED", "accepted"),
            ("PROCESSING", "ocr"),
        ])
        assert resp.status_code == 200

        # Transition to NEEDS_REVIEW
        resp = client.post(
            f"/api/v1/documents/{doc_id}/transition",
            json={"target_status": "NEEDS_REVIEW", "pipeline_stage": "needs_review"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "NEEDS_REVIEW"

        # Mark ready from NEEDS_REVIEW
        resp = client.post(f"/api/v1/documents/{doc_id}/mark-ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "READY"
