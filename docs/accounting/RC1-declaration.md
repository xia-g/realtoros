# Release Candidate 1 (RC1)

**Дата:** 2026-06-17
**Версия:** 1.0.0-rc1
**Система:** Real Estate OS — Accounting Pipeline (Phases 1–7)

---

## 1. Статус

```
SYSTEM STATUS    = RC1
FEATURE FREEZE   = ON
ARCHITECTURE FREEZE = ON
```

## 2. Что заморожено

### Фазы (архитектура frozen)

| Фаза | Название | Статус | Freeze документ |
|------|----------|--------|-----------------|
| Phase 1 | Accounting Core | ❄️ | `docs/accounting/freeze.md` |
| Phase 2 | Decision Engine | ❄️ | `docs/accounting/freeze.md` |
| Phase 2.5 | Production Hardening | ❄️ | `docs/accounting/phase3_freeze.md` |
| Phase 3 | Ledger (Double Entry) | ❄️ | `docs/accounting/phase3_freeze.md` |
| Phase 4 | Tax Registers | ❄️ | `docs/accounting/phase4_freeze.md` |
| Phase 5 | Reporting + AI Audit | ❄️ | `docs/accounting/reporting_boundary.md`, `docs/accounting/report_ai_boundary.md` |
| Phase 6 | Reconciliation | ❄️ | `docs/accounting/reporting_boundary.md` |
| Phase 7 | Control Plane | ❄️ | `docs/accounting/validation/final_report.md` |

### Модель данных (таблицы frozen)

```
accounting schema — 34 миграции, 45+ таблиц:
  ─ accounting_event, accounting_batch, accounting_decision, decision_explanation
  ─ recognition_snapshot, event_transaction, event_document
  ─ tax_regime, tax_period
  ─ chart_of_accounts, posting_batch, posting_decision_link
  ─ ledger_entry, ledger_line
  ─ tax_policy, tax_policy_version, tax_rule
  ─ tax_assignment, tax_register, tax_register_entry, tax_explanation
  ─ report_template, report_template_version, report_draft, report_cell
  ─ report_audit_result, report_audit_finding, submission_package
  ─ reconciliation_run, reconciliation_item, reconciliation_match
  ─ reconciliation_gap, reconciliation_explanation
  ─ system_state, control_action, approval_workflow, system_metrics_snapshot
```

### Инварианты (frozen)

| Инвариант | Слой |
|-----------|------|
| `Decision = f(Event, Snapshot, RulesetVersion)` | P1 |
| `Posting = f(Decision, PostingRulesVersion)` | P3 |
| `Ledger = source of truth` | P3 |
| `Σ debit = Σ credit` | P3 |
| `Tax = f(Ledger, TaxPolicyVersion)` | P4 |
| `one ledger_line → one active assignment` | P4 |
| `Report = f(TaxRegister, ReportTemplateVersion)` | P5 |
| `report_rendering ≠ report_storage` | P5 |
| `generate(register, template) × N = same hash` | P5 |
| `AIAudit(report) → AuditResult` (read-only) | P5 |
| `submission_id ≠ report_id` | P5 |
| `Reconciliation = f(Ledger, BankData, Snapshots)` | P6 |
| `same inputs → same matches → same gaps → same explanations` | P6 |
| `Control Plane does NOT compute data` | P7 |
| AI never approves | P5 |
| Immutable ledger (no UPDATE/DELETE) | P3 |
| Replay creates new version, never mutates old | All |

### API (frozen)

```
base: /api/v1
  /accounting/*    — 4 endpoints
  /ledger/*        — 7 endpoints
  /tax/*           — 12 endpoints
  /reports/*       — 12 endpoints
  /reconciliation/* — 8 endpoints
  /control/*       — 7 endpoints
  total: ~50 endpoints
```

---

## 3. Что разрешено

| Тип | Примеры |
|-----|---------|
| 🐛 Багфиксы | Исправление ошибок в существующей логике, без изменения контрактов |
| 🎨 UX | Улучшение UI, исправление вёрстки, добавление тостов, загрузчиков |
| 📊 Observability | Метрики, логи, алерты, health checks, dashboard |
| 🔌 Импортёры | Адаптеры для импорта банковских выписок, 1С, CRM |
| 🔗 Интеграции | REST API клиенты, webhook handlers, external connectors |

## 4. Что запрещено

| Тип | Примеры |
|-----|---------|
| 🚫 Новые ядровые таблицы | `CREATE TABLE` в schema `accounting` |
| 🚫 Новые состояния | Новые status enums, новые статусные машины |
| 🚫 Новые движки | Новые engine, generator, provider, service классы |
| 🚫 Новые миграции | `alembic revision` для accounting schema |
| 🚫 Новые API endpoints | `@router.get/post` в accounting routes |
| 🚫 Новые инварианты | Изменение формул `f(...)` |

---

## 5. Доказательство готовности

### Validation Track (все 6 этапов пройдены)

| Stage | Результат |
|-------|-----------|
| Smoke tests (20 pages) | ✅ 20/20 |
| Full E2E pipeline (10 steps) | ✅ 10/10 — 19.9s |
| Failure injection (10 scenarios) | ✅ 10/10 |
| Explainability audit (12 chains) | ✅ 12/12 |
| Performance validation | ✅ TTFB <200ms, 50 sessions <500ms |
| **Финальный вывод** | **`READY_FOR_REAL_IMPORT = true`** |

### Quality Gates (все фазы)

| Phase | Gates | Результат |
|-------|-------|-----------|
| Phase 1–3 | — | ✅ Встроено в E2E |
| Phase 4 — Tax | 5 gates | ✅ Все пройдены |
| Phase 5 — Report + AI | 5 gates | ✅ Все пройдены |
| Phase 6 — Reconciliation | 5 gates | ✅ Все пройдены (в E2E) |
| Phase 7 — Control Plane | 5 gates | ✅ Все пройдены |

### Тесты

| Слой | Количество |
|------|-----------|
| Unit tests | ~50 |
| E2E tests (Phase 4) | 7 |
| E2E tests (Phase 5) | 7 |
| E2E tests (Phase 6) | 6 |
| E2E tests (Phase 7) | 5 |
| Validation E2E | 10 |
| Validation failure | 10 |
| Validation explainability | 12 |
| **Total** | **~107 automated tests** |

---

## 6. Версионирование

```
realtoros-accounting v1.0.0-rc1

  ├── backend/main.py       → app.version = "1.0.0-rc1"
  ├── frontend/package.json → "version": "1.0.0-rc1"
  ├── migration head        → 034_control_plane_schema
  └── docs/accounting/validation/final_report.md
```

---

## 7. Подписи

```
Архитектор:        [user]
Релиз-менеджер:    Hermes Agent
Дата:              2026-06-17
Статус:            RC1 — Feature Freeze Active
```
