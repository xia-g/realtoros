"""API smoke — all critical endpoints respond."""
import requests, time

API = "http://localhost:8000/api/v1"
endpoints = [
    ("/accounting/events?limit=5", "events"),
    ("/ledger/entries?limit=5", "ledger entries"),
    ("/tax/registers?limit=5", "tax registers"),
    ("/tax/assignments?limit=5", "tax assignments"),
    ("/tax/policies", "tax policies"),
    ("/tax/periods", "tax periods"),
    ("/reports?limit=5", "reports"),
    ("/reports/templates", "templates"),
    ("/control/state", "control state"),
    ("/control/actions?limit=5", "control actions"),
    ("/control/metrics?limit=5", "metrics"),
    ("/reconciliation/runs?limit=5", "recon runs"),
]

def test_api_smoke():
    print(f"\n{'='*60}")
    print(f"API Smoke — {len(endpoints)} endpoints")
    print(f"{'='*60}")
    print(f"{'Endpoint':40s} {'ms':>6s} {'Status':>8s}")
    print("-"*60)
    passed = 0
    for path, label in endpoints:
        start = time.time()
        try:
            r = requests.get(f"{API}{path}", timeout=10)
            dur = round((time.time() - start) * 1000)
            ok = r.status_code == 200
            status = "PASS" if ok else f"HTTP{r.status_code}"
            if ok: passed += 1
        except Exception as e:
            dur = 0; status = f"ERR:{e}"
        print(f"{label:40s} {dur:6d} {status:>8s}")
    print("-"*60)
    print(f"API: {passed}/{len(endpoints)} passed")
    assert passed == len(endpoints)

if __name__ == "__main__":
    test_api_smoke()
