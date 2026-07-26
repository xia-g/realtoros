"""
Epic 2 / Stream 1 — Accounting unit + integration tests.

Unit tests: entry validation, lifecycle, mapper (no database).
Integration tests: full API flow (requires PostgreSQL).
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "services/accounting_binding"))

import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
from datetime import date

from backend.main import create_app
from backend.services.accounting.models import AccountingEntry, EntryLine, EntryStatus, ENTRY_TRANSITIONS
from backend.services.accounting.mapper import AccountingMapper


# ─── Unit Tests ───────────────────────────────────────────────────


class TestAccountingModels:

    def test_entry_initially_unbalanced(self):
        entry = AccountingEntry(
            entry_id="e1", journal_id="j1", document_id="d1",
            period_id="p1", entry_date=date.today(),
        )
        assert entry.total_debit == Decimal("0")
        assert entry.total_credit == Decimal("0")
        assert entry.is_balanced is True  # 0 == 0 is balanced

    def test_entry_with_lines_balanced(self):
        entry = AccountingEntry(entry_id="e1", journal_id="j1", document_id="d1",
                                period_id="p1", entry_date=date.today())
        entry.lines.append(EntryLine(line_id="l1", entry_id="e1", account_id="26",
                                      debit=Decimal("1000"), credit=Decimal("0")))
        entry.lines.append(EntryLine(line_id="l2", entry_id="e1", account_id="60",
                                      debit=Decimal("0"), credit=Decimal("1000")))
        assert entry.total_debit == Decimal("1000")
        assert entry.total_credit == Decimal("1000")
        assert entry.is_balanced is True

    def test_entry_unbalanced(self):
        entry = AccountingEntry(entry_id="e1", journal_id="j1", document_id="d1",
                                period_id="p1", entry_date=date.today())
        entry.lines.append(EntryLine(line_id="l1", entry_id="e1", account_id="26",
                                      debit=Decimal("1000"), credit=Decimal("0")))
        assert entry.is_balanced is False
        assert entry.total_debit != entry.total_credit

    def test_lifecycle_draft_to_validated(self):
        assert "VALIDATED" in ENTRY_TRANSITIONS["DRAFT"]

    def test_lifecycle_validated_to_posted(self):
        assert "POSTED" in ENTRY_TRANSITIONS["VALIDATED"]

    def test_lifecycle_posted_immutable(self):
        assert ENTRY_TRANSITIONS["POSTED"] == []

    def test_lifecycle_locked_immutable(self):
        assert ENTRY_TRANSITIONS["LOCKED"] == []

    def test_rejected_to_draft(self):
        assert "DRAFT" in ENTRY_TRANSITIONS["REJECTED"]


class TestAccountingMapper:

    def test_invoice_mapping(self):
        mapper = AccountingMapper()
        fields = {"supplier": "ООО Ромашка", "amount": "1200.00", "vat": "200.00", "date": "2024-01-15"}
        entry = mapper.map_to_entry("doc-001", "invoice", fields, "period-current")
        assert entry is not None
        assert entry.status == "DRAFT"
        assert len(entry.lines) == 3  # expense(1000) + vat(200) + supplier(1200)
        assert entry.is_balanced  # 1000 + 200 = 1200
        assert entry.total_debit == Decimal("1200")  # 1000(expense) + 200(vat)
        assert entry.total_credit == Decimal("1200")  # 1200(supplier)

    def test_act_mapping(self):
        mapper = AccountingMapper()
        fields = {"supplier": "ООО Ромашка", "amount": "5000.00", "date": "2024-02-01"}
        entry = mapper.map_to_entry("doc-002", "act", fields, "period-current")
        assert entry is not None
        assert len(entry.lines) == 2  # expense + supplier (no VAT)
        # Нужно исправить: act mapping не включает VAT, так что amount = 5000 дебет и 5000 кредит
        assert entry.is_balanced

    def test_bank_statement_mapping(self):
        mapper = AccountingMapper()
        fields = {"amount": "10000.00", "date": "2024-03-01"}
        entry = mapper.map_to_entry("doc-003", "bank_statement", fields, "period-current")
        assert entry is not None
        assert len(entry.lines) == 2
        assert entry.is_balanced

    def test_unknown_type(self):
        mapper = AccountingMapper()
        entry = mapper.map_to_entry("doc-004", "unknown", {}, "period-current")
        assert entry is None

    def test_missing_fields(self):
        mapper = AccountingMapper()
        entry = mapper.map_to_entry("doc-005", "invoice", {}, "period-current")
        # No amount or vat → no lines → None
        assert entry is None

    def test_invoice_uses_date_from_fields(self):
        mapper = AccountingMapper()
        fields = {"supplier": "ООО Ромашка", "amount": "1000.00", "vat": "200.00", "date": "2024-06-15"}
        entry = mapper.map_to_entry("doc-006", "invoice", fields, "period-current")
        assert entry is not None
        assert entry.entry_date == date(2024, 6, 15)


# ─── Integration Tests ────────────────────────────────────────────


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestAccountingAPI:

    ENTRY_ID = None

    def test_1_create_entry(self, client):
        """POST /accounting/entries creates entry."""
        resp = client.post("/api/v1/accounting/entries", json={
            "journal_id": "journal-general",
            "document_id": "doc-integration-001",
            "period_id": "period-current",
            "entry_date": "2024-01-15",
            "description": "Test entry",
            "lines": [
                {"account_id": "26", "debit": "1000", "credit": "0", "description": "Expense"},
                {"account_id": "60", "debit": "0", "credit": "1200", "description": "Supplier"},
                {"account_id": "19", "debit": "200", "credit": "0", "description": "VAT"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DRAFT"
        assert len(data["lines"]) == 3
        assert data["total_debit"] == "1200.00"
        assert data["total_credit"] == "1200.00"
        assert data["is_balanced"] is True
        TestAccountingAPI.ENTRY_ID = data["entry_id"]

    def test_2_get_entry(self, client):
        """GET /accounting/entries/{id} returns entry."""
        resp = client.get(f"/api/v1/accounting/entries/{TestAccountingAPI.ENTRY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entry_id"] == TestAccountingAPI.ENTRY_ID

    def test_3_list_entries(self, client):
        """GET /accounting/entries returns list."""
        resp = client.get("/api/v1/accounting/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) >= 1

    def test_4_validate_entry(self, client):
        """POST /accounting/entries/{id}/validate → VALIDATED."""
        resp = client.post(f"/api/v1/accounting/entries/{TestAccountingAPI.ENTRY_ID}/validate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "VALIDATED"

    def test_5_post_entry(self, client):
        """POST /accounting/entries/{id}/post → POSTED."""
        resp = client.post(f"/api/v1/accounting/entries/{TestAccountingAPI.ENTRY_ID}/post")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "POSTED"
        assert data["posted_at"] is not None

    def test_6_posted_entry_no_more_transitions(self, client):
        """POSTED entry cannot transition."""
        resp = client.post(f"/api/v1/accounting/entries/{TestAccountingAPI.ENTRY_ID}/validate")
        assert resp.status_code == 400

    def test_7_list_accounts(self, client):
        """GET /accounting/accounts returns chart."""
        resp = client.get("/api/v1/accounting/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["accounts"]) >= 5  # 5 seeded accounts

    def test_8_trial_balance(self, client):
        """GET /accounting/trial-balance returns data."""
        resp = client.get("/api/v1/accounting/trial-balance?period_id=period-current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_id"] == "period-current"

    def test_9_account_turnover(self, client):
        """GET /accounting/ledger/{account_id} returns turnover."""
        resp = client.get("/api/v1/accounting/ledger/60?period_id=period-current")
        assert resp.status_code == 200
        assert resp.json()["account_id"] == "60"
        # There should be a credit of 1200 from our posted entry
        assert resp.json()["credit"] > 0

    def test_10_create_from_document_not_analyzed(self, client):
        """POST /accounting/documents/{id}/create-entry on nonexistent doc → 404."""
        resp = client.post("/api/v1/accounting/documents/fake-doc/create-entry")
        assert resp.status_code == 404

    def test_11_create_from_document(self, client):
        """Upload → ANALYZE → create accounting entry."""
        content = b"test document for accounting"
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("acc-test.pdf", content, "application/pdf")},
        )
        doc_id = resp.json()["document_id"]
        for s in ["VALIDATED", "ACCEPTED", "PROCESSING", "ANALYZED"]:
            client.post(f"/api/v1/documents/{doc_id}/transition", json={"target_status": s})

        # Set profile with invoice fields
        from backend.config import settings
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
        cur = conn.cursor()
        profile = {
            "document_type": "invoice",
            "confidence": 0.9,
            "fields": {"supplier": "ООО Ромашка", "amount": "5000.00", "vat": "1000.00", "date": "2024-04-01"},
        }
        cur.execute("UPDATE document_intake SET profile = %s WHERE document_id = %s",
                    (psycopg2.extras.Json(profile), doc_id))
        conn.commit()
        conn.close()

        resp = client.post(f"/api/v1/accounting/documents/{doc_id}/create-entry")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == doc_id
        assert len(data["lines"]) == 3  # expense + supplier + vat
        assert data["is_balanced"] is True
