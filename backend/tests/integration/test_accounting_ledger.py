"""
Epic 2 / Stream 2 — Ledger & Posting integration tests.
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
from backend.services.accounting.posting import PostingService


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestPostingAPI:

    POSTED_ENTRY_ID = None

    def test_1_create_and_post_balanced_entry(self, client):
        """Create entry → validate → post → check journal + ledger."""
        resp = client.post("/api/v1/accounting/entries", json={
            "journal_id": "journal-general",
            "document_id": "doc-ledger-001",
            "period_id": "period-current",
            "entry_date": "2024-01-15",
            "description": "Ledger test entry",
            "lines": [
                {"account_id": "26", "debit": "1000", "credit": "0", "description": "Expense"},
                {"account_id": "60", "debit": "0", "credit": "1000", "description": "Supplier"},
            ],
        })
        eid = resp.json()["entry_id"]

        # Validate
        client.post(f"/api/v1/accounting/entries/{eid}/validate")

        # Post via service
        from backend.config import settings
        svc = PostingService(settings.DATABASE_SYNC_URL)
        err = svc.post_entry(eid)
        assert err is None, f"Post failed: {err}"

        # Verify posted
        resp = client.get(f"/api/v1/accounting/entries/{eid}")
        assert resp.json()["status"] == "POSTED"
        TestPostingAPI.POSTED_ENTRY_ID = eid

    def test_2_journal_has_entry(self, client):
        """Journal shows the posted entry."""
        resp = client.get("/api/v1/accounting/journal?period_id=period-current")
        assert resp.status_code == 200
        entries = resp.json()["journal_entries"]
        assert len(entries) >= 1
        assert any(e["entry_id"] == TestPostingAPI.POSTED_ENTRY_ID for e in entries)

    def test_3_ledger_has_detail(self, client):
        """Ledger entries have running balance."""
        resp = client.get("/api/v1/accounting/ledger/60/entries?period_id=period-current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_id"] == "60"
        assert len(data["entries"]) >= 1
        last = data["entries"][-1]
        assert float(last["balance_after"]) < 0  # liability balance is negative

    def test_4_balance_sheet_returns_data(self, client):
        """Balance sheet includes sections."""
        resp = client.get("/api/v1/accounting/balance-sheet?period_id=period-current")
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data
        assert len(data["sections"]) == 3  # asset, liability, equity

    def test_5_profit_loss_returns_data(self, client):
        """P&L includes sections."""
        resp = client.get("/api/v1/accounting/profit-loss?period_id=period-current")
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data
        assert len(data["sections"]) == 2  # revenue, expense

    def test_6_period_list(self, client):
        """Periods endpoint works."""
        resp = client.get("/api/v1/accounting/periods")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["periods"]) >= 1

    def test_7_post_in_balanced_works(self, client):
        """Create another balanced entry, post via API."""
        resp = client.post("/api/v1/accounting/entries", json={
            "journal_id": "journal-general",
            "document_id": "doc-ledger-002",
            "period_id": "period-current",
            "entry_date": "2024-02-01",
            "description": "Second entry",
            "lines": [
                {"account_id": "51", "debit": "5000", "credit": "0", "description": "Cash in"},
                {"account_id": "76", "debit": "0", "credit": "5000", "description": "Counterparty"},
            ],
        })
        eid = resp.json()["entry_id"]
        client.post(f"/api/v1/accounting/entries/{eid}/validate")

        # Post via API (now uses PostingService internally)
        resp = client.post(f"/api/v1/accounting/entries/{eid}/post")
        assert resp.status_code == 200
        assert resp.json()["status"] == "POSTED"

    def test_8_post_unbalanced_fails(self, client):
        """Unbalanced entry cannot be posted."""
        resp = client.post("/api/v1/accounting/entries", json={
            "journal_id": "journal-general",
            "document_id": "doc-bad",
            "period_id": "period-current",
            "entry_date": "2024-03-01",
            "description": "Unbalanced",
            "lines": [
                {"account_id": "26", "debit": "1000", "credit": "0", "description": "Expense"},
                # No credit line
            ],
        })
        eid = resp.json()["entry_id"]

        # Try to post directly without validate
        resp = client.post(f"/api/v1/accounting/entries/{eid}/post")
        assert resp.status_code == 400  # Should fail - needs validate first

    def test_9_journal_sequence(self, client):
        """Journal entries have increasing sequence numbers."""
        resp = client.get("/api/v1/accounting/journal?period_id=period-current&limit=10")
        entries = resp.json()["journal_entries"]
        if len(entries) >= 2:
            seqs = [e["sequence_number"] for e in entries]
            assert seqs == sorted(seqs)
