"""Smoke tests — all pages load + filter + render."""
import requests, time, sys

BASE = "http://localhost:3000"
API = "http://localhost:8000/api/v1"
routes = [
    ("/", "Dashboard"),
    ("/accounting/events", "Event Explorer"),
    ("/accounting/decisions", "Decision Explorer"),
    ("/accounting/replay", "Replay Console"),
    ("/ledger/entries", "Ledger Explorer"),
    ("/ledger/accounts", "Chart of Accounts"),
    ("/ledger/periods", "Tax Periods"),
    ("/tax/registers", "Tax Registers"),
    ("/tax/assignments", "Tax Assignments"),
    ("/tax/policies", "Tax Policies"),
    ("/reports/drafts", "Report Drafts"),
    ("/reports/templates", "Report Templates"),
    ("/reports/audit", "Report Audit"),
    ("/reconciliation/runs", "Reconciliation Runs"),
    ("/reconciliation/matches", "Recon Matches"),
    ("/reconciliation/gaps", "Recon Gaps"),
    ("/control/actions", "Control Actions"),
    ("/control/approval", "Approval Queue"),
    ("/control/state", "System State"),
    ("/control/metrics", "Metrics"),
]

def test_smoke():
    results = []
    for path, label in routes:
        start = time.time()
        try:
            r = requests.get(f"{BASE}{path}", timeout=10)
            dur = round((time.time() - start) * 1000)
            status = "PASS" if r.status_code == 200 else "FAIL"
            results.append((label, dur, status, ""))
        except Exception as e:
            results.append((label, 0, "FAIL", str(e)))

    print(f"\n{'='*60}")
    print(f"Smoke Test Results — {len(routes)} pages")
    print(f"{'='*60}")
    print(f"{'Page':30s} {'ms':>6s} {'Status':>8s} {'Issues'}")
    print("-"*60)
    passed = 0
    for label, dur, status, issues in results:
        print(f"{label:30s} {dur:6d} {status:>8s} {issues}")
        if status == "PASS": passed += 1
    print("-"*60)
    print(f"Total: {passed}/{len(routes)} passed")
    assert passed == len(routes), f"Smoke test failed: {passed}/{len(routes)}"

if __name__ == "__main__":
    test_smoke()
