# Full Accounting Scenario — E2E Results

## Flow

```
Decision → Posting → Ledger → Tax Assignment → Register → Report → AI Audit → Submission → Reconciliation → Approval → Close Period
```

## Timings

| Step | Operation | Duration | Status |
|------|-----------|----------|--------|
| 1 | Import → Event + Decision | <500ms | ✅ |
| 2 | Post → Ledger entry | <500ms | ✅ |
| 3 | Ledger → Tax Assignment | <500ms | ✅ |
| 4 | Tax Assignment → Register | <500ms | ✅ |
| 5 | Register → Report | <500ms | ✅ |
| 6 | Report → AI Audit | <500ms | ✅ |
| 7 | Report → Submission | <500ms | ✅ |
| 8 | Full → Reconciliation | <5s | ✅ |
| 9 | Control → Approval | <500ms | ✅ |
| 10 | Approval → Close Period | <500ms | ✅ |

## Hashes

| Artifact | Hash |
|----------|------|
| Posting hash | deterministic SHA256 |
| Report hash | SHA256(template + register + cells) |
| Run hash | SHA256(matches + gaps) |
| Action state hash | SHA256(subsystem counts) |

## Screenshots

See `screenshots/` directory (captured via Playwright).

## Key Invariants Verified

- [x] same inputs → same report hash
- [x] submission_id ≠ report_id
- [x] AI audit does not change report cells
- [x] reconciliation does not change ledger
- [x] replay → identical hash
