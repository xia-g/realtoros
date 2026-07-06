# Explainability Audit — Results

## Chain Coverage

| # | Chain | Status | Detail |
|---|-------|--------|--------|
| 1 | Event → why created | ✅ | event_type, amount, source_type |
| 2 | Decision → why included | ✅ | reason field populated |
| 3 | Decision → explanations | ✅ | rule_code, weight, message |
| 4 | Posting → why posted | ✅ | posting_rule_code, version |
| 5 | Tax Assignment → why taxed | ✅ | register_type, reason_code |
| 6 | Register Entry → explainable | ✅ | full chain to decision_explanation |
| 7 | Report → why reported | ✅ | template_version, status, hash |
| 8 | Report Cell → has source_hash | ✅ | SHA256 of inputs |
| 9 | Audit Finding → explained | ✅ | severity, category, description |
| 10 | Reconciliation Gap → explained | ✅ | gap_type, severity, description |
| 11 | Control Action → who acted | ✅ | actor_id, actor_role |
| 12 | Approval → who approved | ✅ | approved_by, reason |

## Broken Chains

None — all 12 chains proven.

## Missing Explanations

| Entity | Missing | Priority |
|--------|---------|----------|
| — | none | — |
