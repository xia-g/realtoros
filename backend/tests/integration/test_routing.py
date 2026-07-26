"""
Epic 1 / Stream 3 — Routing unit and integration tests.

Unit tests for RoutingEngine (no database).
Integration tests for Routing API (requires PostgreSQL).
"""
from __future__ import annotations

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "services/accounting_binding"))

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.routing.models import RoutingEngine, RoutingRule


# ─── Unit Tests ───────────────────────────────────────────────────


class TestRoutingEngine:

    def test_invoice_to_accounting(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "invoice",
            "confidence": 0.85,
        })
        assert result.destination == "accounting"
        assert result.matched is True

    def test_invoice_low_confidence_fallback(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "invoice",
            "confidence": 0.5,
        })
        # Below 0.7 threshold, should fall to default
        assert result.destination == "needs_review"

    def test_contract_to_deal(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "contract",
            "confidence": 0.75,
        })
        assert result.destination == "deal"
        assert result.needs_approval is True

    def test_act_to_accounting(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "act",
            "confidence": 0.8,
        })
        assert result.destination == "accounting"

    def test_bank_statement_to_accounting(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "bank_statement",
            "confidence": 0.65,
        })
        assert result.destination == "accounting"

    def test_bank_statement_low_confidence(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "bank_statement",
            "confidence": 0.4,
        })
        assert result.destination == "needs_review"

    def test_passport_to_crm(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "passport",
            "confidence": 0.0,
        })
        assert result.destination == "crm"
        assert result.needs_approval is True

    def test_unknown_document(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "unknown",
            "confidence": 0.0,
        })
        # There IS a matching rule (default → needs_review), so matched=True
        assert result.destination == "needs_review"
        assert result.matched is True  # default rule matched

    def test_empty_profile(self):
        engine = RoutingEngine()
        result = engine.evaluate({})
        # Empty → unknown type → default rule → needs_review
        assert result.destination == "needs_review"
        assert result.matched is True

    def test_uses_best_confidence(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "invoice",
            "confidence": 0.0,
            "extraction_confidence": 0.85,
        })
        assert result.destination == "accounting"

    def test_priority_rules(self):
        # Add a higher priority rule
        high_prio = RoutingRule(
            rule_id="test-hi",
            name="High Priority",
            document_type="invoice",
            condition="True",
            destination="crm",
            priority=100,
            min_confidence=0.0,
            needs_approval=False,
        )
        engine = RoutingEngine(rules=[high_prio])
        result = engine.evaluate({
            "document_type": "invoice",
            "confidence": 0.9,
        })
        assert result.destination == "crm"

    def test_receipt_to_accounting(self):
        engine = RoutingEngine()
        result = engine.evaluate({
            "document_type": "receipt",
            "confidence": 0.7,
        })
        assert result.destination == "accounting"


# ─── Integration Tests ────────────────────────────────────────────


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestRoutingAPI:

    ROUTED_DOC_ID = None

    def test_1_route_nonexistent_document(self, client):
        """POST /routing/documents/{id}/route on missing doc → 404."""
        resp = client.post("/api/v1/routing/documents/fake-id/route")
        assert resp.status_code == 404

    def test_2_upload_and_analyze(self, client):
        """Upload → ACCEPTED → (mock pipeline sets ANALYZED)."""
        content = b"test document content"
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("routing-test.pdf", content, "application/pdf")},
            data={"organization_id": "org-001"},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["document_id"]

        # Transition to ACCEPTED, then PROCESSING, then ANALYZED
        for status in ["VALIDATED", "ACCEPTED", "PROCESSING", "ANALYZED"]:
            resp = client.post(
                f"/api/v1/documents/{doc_id}/transition",
                json={"target_status": status},
            )
            assert resp.status_code == 200

        # Set profile with document type and confidence
        doc = resp.json()
        TestRoutingAPI.ROUTED_DOC_ID = doc_id
        return doc_id

    def test_3_route_invoice(self, client):
        """POST /routing/documents/{id}/route → DECIDED/ROUTED."""
        doc_id = TestRoutingAPI.ROUTED_DOC_ID
        # Need to manually set profile since there's no pipeline
        # Update document profile via DB
        from backend.config import settings
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
        cur = conn.cursor()
        profile = {
            "document_type": "invoice",
            "confidence": 0.88,
            "extraction_confidence": 0.85,
            "classification_confidence": 0.9,
            "fields": {"supplier": "ООО Ромашка", "amount": "1000", "date": "01.01.2024"},
        }
        cur.execute(
            "UPDATE document_intake SET profile = %s WHERE document_id = %s",
            (psycopg2.extras.Json(profile), doc_id),
        )
        conn.commit()
        conn.close()

        resp = client.post(f"/api/v1/routing/documents/{doc_id}/route")
        assert resp.status_code == 200
        data = resp.json()
        assert data["destination"] == "accounting"
        assert data["status"] in ("ROUTED", "DECIDED")
        assert data["confidence"] > 0.7

    def test_4_get_document_route(self, client):
        """GET /routing/documents/{id}/route returns decision."""
        resp = client.get(f"/api/v1/routing/documents/{TestRoutingAPI.ROUTED_DOC_ID}/route")
        assert resp.status_code == 200
        data = resp.json()
        assert data["destination"] == "accounting"

    def test_5_get_decision(self, client):
        """GET /routing/decisions/{id} returns full decision."""
        resp = client.get(f"/api/v1/routing/documents/{TestRoutingAPI.ROUTED_DOC_ID}/route")
        dec_id = resp.json()["decision_id"]
        resp = client.get(f"/api/v1/routing/decisions/{dec_id}")
        assert resp.status_code == 200
        assert resp.json()["decision_id"] == dec_id

    def test_6_override_decision(self, client):
        """POST override changes destination."""
        resp = client.get(f"/api/v1/routing/documents/{TestRoutingAPI.ROUTED_DOC_ID}/route")
        dec_id = resp.json()["decision_id"]

        resp = client.post(
            f"/api/v1/routing/decisions/{dec_id}/override",
            json={"destination": "deal"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OVERRIDDEN"
        assert data["destination"] == "deal"

    def test_7_route_needs_review(self, client):
        """Low confidence → needs_review."""
        # Upload new doc
        content = b"unknown content"
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("unknown.pdf", content, "application/pdf")},
        )
        doc_id = resp.json()["document_id"]
        for status in ["VALIDATED", "ACCEPTED", "PROCESSING", "ANALYZED"]:
            client.post(f"/api/v1/documents/{doc_id}/transition", json={"target_status": status})

        # Set profile with unknown type
        from backend.config import settings
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
        cur = conn.cursor()
        profile = {"document_type": "unknown", "confidence": 0.0, "fields": {}}
        cur.execute(
            "UPDATE document_intake SET profile = %s WHERE document_id = %s",
            (psycopg2.extras.Json(profile), doc_id),
        )
        conn.commit()
        conn.close()

        resp = client.post(f"/api/v1/routing/documents/{doc_id}/route")
        assert resp.status_code == 200
        assert resp.json()["destination"] == "needs_review"
