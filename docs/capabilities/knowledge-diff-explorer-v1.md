# Knowledge Diff Explorer v1 — Capability Report

```
Capability        Knowledge Diff Explorer v1
──────────────────────────────────────────────
Status            COMPLETE
──────────────────────────────────────────────
Architecture      v2.3.1
Baseline
──────────────────────────────────────────────
Platform          0 files
changes
──────────────────────────────────────────────
ADR               Not required
──────────────────────────────────────────────
Architecture      Not required
Review
──────────────────────────────────────────────
Regression        1056 / 1056 PASS
──────────────────────────────────────────────
Branch            feature/knowledge-diff-explorer-v1
──────────────────────────────────────────────
Date              2026-07-21
```

## Acceptance Checklist

| Критерий | Результат |
|----------|:---------:|
| Platform files changed = 0 | ✅ |
| ADR required = No | ✅ |
| Architecture Review = No | ✅ |
| Existing regressions = PASS | ✅ 1056/1056 |
| Diff deterministic (same input → same output) | ✅ |
| Graph comparison deterministic | ✅ |
| Snapshot unchanged (read-only comparison) | ✅ |
| Explorer compatibility preserved | ✅ 7/7 |
| Timeline compatibility preserved | ✅ 12/12 |
| Covered by tests | ✅ 41 tests (32 unit + 9 API) |

## Diff Invariants

| Invariant | Status | Test |
|-----------|:------:|------|
| Diff(A, A) → empty | ✅ | `test_same_snapshot_empty_diff` |
| Deterministic | ✅ | `test_deterministic` |
| Order-independent | ✅ | `test_order_independent` |
| Snapshot unchanged | ✅ | `test_snapshot_unchanged` |

## Identity Contract (Phase 0 Validation)

| Key | Expected | Actual | Used in Diff |
|-----|:--------:|:------:|:------------:|
| Node: `node_id` | stable | ❌ random uuid4 | No (metadata) |
| Node: `(node_type, domain_id)` | — | ✅ stable | **Yes** |
| Edge: `edge_id` | — | ❌ random uuid4 | No (metadata) |
| Edge: `(source_key, type, target_key)` | — | ✅ semantic | **Yes** |
| Provenance: `(source_type, source_id)` | — | ✅ stable | **Yes** |
| Explanation: `step_number` | — | ✅ monotonic | **Yes** |

## Endpoint

```
GET /knowledge/revisions/{left_revision_id}/diff/{right_revision_id}
```

Response: `{nodes: {added, removed, updated}, edges: {added, removed},
provenance: {added, removed}, explanation: {added, removed, changed},
summary: {counts}}`

## Architecture Significance

Третья независимая read-oriented Capability, реализованная
поверх Platform v2.3.1 без архитектурных изменений.

Каждая из трёх Capability использует Platform по-разному:

1. **Explorer** — чтение состояния одной Revision
2. **Timeline** — навигация по истории (cursor-based pagination)
3. **Diff Explorer** — вычисление изменений между двумя состояниями

Все три — с результатом `Platform files changed = 0`.

## Test Results

| Suite | Tests | Status |
|-------|:-----:|:------:|
| Platform (accounting_binding) | 996 | ✅ |
| Diff unit (nodes, edges, provenance, explanation) | 32 | ✅ |
| Diff API (endpoint, empty, 404, summary) | 9 | ✅ |
| Explorer compatibility | 7 | ✅ |
| Timeline compatibility | 12 | ✅ |
| **Total** | **1056** | ✅ |

## Conclusion

Capability полностью реализована поверх Platform v2.3.1
без архитектурных изменений. Baseline intact.

Knowledge Diff Explorer — третья Capability, подтверждающая,
что выбранные границы Architecture Baseline v2.3.1
действительно позволяют развивать продукт через независимые
Capability без модификации ядра.
