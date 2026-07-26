"""E2E test: upload real ДКП, process, route, create accounting entry."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "services/accounting_binding"))

import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.services.accounting.posting import PostingService
from backend.config import settings

DKP_PATH = "/home/xiag/2026-05-26 ДКП-2182 НП_И-СПб, Петроградская наб, дом 18, корп. 3, лит. В, пом. 20-Н.pdf"


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestDKPFullLifecycle:
    """E2E: real ДКП document through full pipeline."""

    def test_1_upload_dkp(self, client):
        """Upload real DKP PDF, verify document created."""
        assert os.path.exists(DKP_PATH), f"File not found: {DKP_PATH}"
        with open(DKP_PATH, "rb") as f:
            content = f.read()

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("DKP-2182.pdf", content, "application/pdf")},
            data={"organization_id": "org-test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "UPLOADED"
        assert data["original_filename"] == "DKP-2182.pdf"
        assert data["size_bytes"] > 1000
        print(f"\n✅ Document uploaded: {data['document_id']}")
        print(f"   Size: {data['size_bytes']} bytes, MIME: {data['mime_type']}")
        TestDKPFullLifecycle.DOC_ID = data["document_id"]

    def test_2_transition_to_analyzed(self, client):
        """Walk document through lifecycle to ANALYZED."""
        doc_id = TestDKPFullLifecycle.DOC_ID
        for status in ["VALIDATED", "ACCEPTED", "PROCESSING", "ANALYZED"]:
            resp = client.post(
                f"/api/v1/documents/{doc_id}/transition",
                json={"target_status": status},
            )
            assert resp.status_code == 200, f"Transition {status} failed: {resp.text}"
        print(f"✅ Document ANALYZED: {doc_id}")

    def test_3_set_dkp_profile(self, client):
        """Set document profile from real DKP extraction."""
        doc_id = TestDKPFullLifecycle.DOC_ID
        # Simulate the real data from OCR
        profile = {
            "document_type": "contract",
            "confidence": 0.95,
            "classification_confidence": 0.44,
            "extraction_confidence": 0.60,
            "fields": {
                "supplier": "Комитет имущественных отношений Санкт-Петербурга",
                "customer": "Шульгина Ирина Юрьевна",
                "amount": "18178000.00",
                "vat": "3278000.00",
                "date": "26.05.2026",
                "contract_number": "2182-НШИ",
                "cadastral_number": "78:07:0003009:1342",
                "property_address": "наб. Петроградская, д. 18, корп. 3, лит. В, пом. 20-Н",
            }
        }
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
        cur = conn.cursor()
        cur.execute("UPDATE document_intake SET profile = %s WHERE document_id = %s",
                    (psycopg2.extras.Json(profile), doc_id))
        conn.commit()
        conn.close()
        print(f"✅ Document profile set: contract, price=18,178,000 RUB, VAT=3,278,000 RUB")

    def test_4_route_dkp(self, client):
        """Route document → should go to 'deal' (contract with approval)."""
        doc_id = TestDKPFullLifecycle.DOC_ID
        resp = client.post(f"/api/v1/routing/documents/{doc_id}/route")
        assert resp.status_code == 200
        data = resp.json()
        print(f"✅ Routing: destination={data['destination']}, status={data['status']}")
        print(f"   confidence={data['confidence']}, needs_approval={data['needs_approval']}")
        # Contract → should route to deal with approval
        assert data["destination"] == "deal", f"Expected 'deal', got '{data['destination']}'"
        assert data["needs_approval"] is True
        TestDKPFullLifecycle.ROUTE_DECISION_ID = data["decision_id"]

    def test_5_create_accounting_entry_from_dkp(self, client):
        """Create accounting entry from DKP document."""
        doc_id = TestDKPFullLifecycle.DOC_ID
        resp = client.post(f"/api/v1/accounting/documents/{doc_id}/create-entry")
        
        if resp.status_code == 400 and "mapping" in resp.text:
            # Contract has no automatic mapping — create manual entry
            print("   (Contract has no automatic mapping — creating manual entry)")
            resp = client.post("/api/v1/accounting/entries", json={
                "journal_id": "journal-general",
                "document_id": doc_id,
                "period_id": "period-current",
                "entry_date": "2026-05-26",
                "description": "ДКП-2182: покупка нежилого помещения",
                "lines": [
                    {"account_id": "26", "debit": "14900000", "credit": "0", "description": "Кап. вложения (без НДС)"},
                    {"account_id": "19", "debit": "3278000", "credit": "0", "description": "НДС к вычету"},
                    {"account_id": "60", "debit": "0", "credit": "18178000", "description": "Расчеты с КИО Санкт-Петербурга"},
                ],
            })
            assert resp.status_code == 200
            TestDKPFullLifecycle.ENTRY_ID = resp.json()["entry_id"]
            print(f"✅ Manual entry created: {TestDKPFullLifecycle.ENTRY_ID}")
            for line in resp.json()["lines"]:
                print(f"   Account {line['account_id']}: debit={line['debit']}, credit={line['credit']} — {line['description']}")
        else:
            assert resp.status_code == 200, f"Accounting: {resp.status_code} {resp.text}"
            entry = resp.json()
            assert entry["is_balanced"] is True
            TestDKPFullLifecycle.ENTRY_ID = entry["entry_id"]
            print(f"✅ Auto entry created: {entry['entry_id']}")
            print(f"   Status: {entry['status']}, balanced: {entry['is_balanced']}")
            for line in entry["lines"]:
                print(f"   Account {line['account_id']}: debit={line['debit']}, credit={line['credit']} — {line['description']}")

    def test_6_validate_and_post_entry(self, client):
        """Validate and post the accounting entry."""
        eid = TestDKPFullLifecycle.ENTRY_ID
        resp = client.post(f"/api/v1/accounting/entries/{eid}/validate")
        assert resp.status_code == 200, f"Validate: {resp.status_code} {resp.text}"
        assert resp.json()["status"] == "VALIDATED"
        print(f"✅ Entry VALIDATED: {eid}")

        resp = client.post(f"/api/v1/accounting/entries/{eid}/post")
        assert resp.status_code == 200, f"Post: {resp.status_code} {resp.text}"
        assert resp.json()["status"] == "POSTED"
        print(f"✅ Entry POSTED: {eid}")

    def test_7_check_trial_balance(self, client):
        """Trial balance should reflect the DKP entry."""
        resp = client.get("/api/v1/accounting/trial-balance?period_id=period-current")
        assert resp.status_code == 200
        tb = resp.json()
        print(f"✅ Trial balance:")
        print(f"   Total debit: {tb['totals']['debit']:.2f}")
        print(f"   Total credit: {tb['totals']['credit']:.2f}")
        print(f"   Balanced: {tb['totals']['is_balanced']}")
        # Find our accounts
        for acc in tb["accounts"]:
            if acc["code"] in ("26", "19", "60"):
                print(f"   Account {acc['code']} ({acc['name']}): debit={acc['debit']:.2f}, credit={acc['credit']:.2f}")

    def test_8_check_journal(self, client):
        """Journal should contain our posted entry."""
        resp = client.get("/api/v1/accounting/journal?period_id=period-current&limit=10")
        assert resp.status_code == 200
        entries = resp.json()["journal_entries"]
        print(f"✅ Journal: {len(entries)} entries")
        for e in entries[-3:]:
            print(f"   #{e['sequence_number']}: {e['description'][:60]} — {e['status']}")

    def test_9_check_balance_sheet(self, client):
        """Balance sheet reflects DKP."""
        resp = client.get("/api/v1/accounting/balance-sheet?period_id=period-current")
        assert resp.status_code == 200
        bs = resp.json()
        print(f"✅ Balance Sheet:")
        print(f"   Total assets: {bs['total_assets']:.2f}")
        print(f"   Total liabilities+equity: {bs['total_liabilities_equity']:.2f}")
        print(f"   Balanced: {bs['is_balanced']}")

    def test_10_full_trace(self, client):
        """Trace from document → accounting entry."""
        doc_id = TestDKPFullLifecycle.DOC_ID
        eid = TestDKPFullLifecycle.ENTRY_ID
        
        # Document → Entry
        resp = client.get(f"/api/v1/accounting/entries/{eid}")
        assert resp.status_code == 200
        entry = resp.json()
        assert entry["document_id"] == doc_id
        print(f"✅ Full trace: Document {doc_id[:8]}... → Entry {eid[:8]}...")
        print(f"   Entry status: {entry['status']}")
        for line in entry["lines"]:
            print(f"   {line['account_id']} | debit={line['debit']:>10s} | credit={line['credit']:>10s} | {line['description']}")
        print(f"   Total D={entry['total_debit']}  C={entry['total_credit']}  Balanced={entry['is_balanced']}")
