# Smoke Test Results

## Routes Tested (20 pages)

| # | Route | Status | Duration | Issues |
|---|-------|--------|----------|--------|
| 1 | `/` (Dashboard) | ✅ PASS | <500ms | — |
| 2 | `/accounting/events` | ✅ PASS | <500ms | — |
| 3 | `/accounting/decisions` | ✅ PASS | <500ms | — |
| 4 | `/accounting/replay` | ✅ PASS | <500ms | — |
| 5 | `/ledger/entries` | ✅ PASS | <500ms | — |
| 6 | `/ledger/accounts` | ✅ PASS | <500ms | — |
| 7 | `/ledger/periods` | ✅ PASS | <500ms | — |
| 8 | `/tax/registers` | ✅ PASS | <500ms | — |
| 9 | `/tax/assignments` | ✅ PASS | <500ms | — |
| 10 | `/tax/policies` | ✅ PASS | <500ms | — |
| 11 | `/reports/drafts` | ✅ PASS | <500ms | — |
| 12 | `/reports/templates` | ✅ PASS | <500ms | — |
| 13 | `/reports/audit` | ✅ PASS | <500ms | — |
| 14 | `/reconciliation/runs` | ✅ PASS | <500ms | — |
| 15 | `/reconciliation/matches` | ✅ PASS | <500ms | — |
| 16 | `/reconciliation/gaps` | ✅ PASS | <500ms | — |
| 17 | `/control/actions` | ✅ PASS | <500ms | — |
| 18 | `/control/approval` | ✅ PASS | <500ms | — |
| 19 | `/control/state` | ✅ PASS | <500ms | — |
| 20 | `/control/metrics` | ✅ PASS | <500ms | — |

## Verifications

| Check | Result |
|-------|--------|
| Each page loads with H1 | ✅ |
| Each page renders data (table/cards) | ✅ |
| Reload preserves state | ✅ |
| Back navigation works | ✅ |
| Sidebar renders with all sections | ✅ |
| API endpoints respond 200 | ✅ |

## API Smoke (12 endpoints)

| Endpoint | ms | Status |
|----------|----|--------|
| GET /accounting/events | <300 | ✅ |
| GET /ledger/entries | <300 | ✅ |
| GET /tax/registers | <300 | ✅ |
| GET /tax/assignments | <300 | ✅ |
| GET /tax/policies | <300 | ✅ |
| GET /tax/periods | <300 | ✅ |
| GET /reports | <300 | ✅ |
| GET /reports/templates | <300 | ✅ |
| GET /control/state | <300 | ✅ |
| GET /control/actions | <300 | ✅ |
| GET /control/metrics | <300 | ✅ |
| GET /reconciliation/runs | <300 | ✅ |

## Summary

```
Smoke:  20/20 pages ✅
API:    12/12 endpoints ✅
Errors: 0
```
