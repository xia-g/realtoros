# Phase 4 — Deterministic Tax Projection Layer

**Дата:** 2026-06-16
**Статус:** ❄️ **Реализовано и заморожено**
**E2E:** 7/7 ✅ | **Quality Gates:** 5/5 ✅

---

## 1. ERD Tax Layer

```
┌─────────────────────────────────────────────────────────────┐
│                     TAX LAYER (Phase 4)                     │
│                                                             │
│  tax_policy (1) ──→ (N) tax_policy_version (1) ──→ (N)     │
│    name, tax_regime        version, effective_from,         │
│    is_active               effective_to, rules_hash         │
│                                                             │
│  tax_policy_version (1) ──→ (N) tax_rule                   │
│                              priority, rule_code,           │
│                              account_pattern, direction,    │
│                              register_type, tax_treatment,  │
│                              excluded, reason_code          │
│                                                             │
│  ledger_line (1) ──→ (N) tax_assignment (N) ──→ (1)        │
│                        ledger_line_id                       │
│                        ledger_entry_id                      │
│                        company_id                           │
│                        policy_version_id                    │
│                        register_type                        │
│                        tax_treatment                        │
│                        excluded                             │
│                        reason_code                          │
│                        is_current                           │
│                        superseded_by                        │
│                        version                              │
│                                                             │
│  tax_assignment (1) ──→ (N) tax_register_entry              │
│                              register_id                    │
│                              assignment_id                  │
│                              ledger_line_id                 │
│                              account_code                   │
│                              amount                         │
│                              direction                      │
│                              tax_treatment                  │
│                              excluded                       │
│                                                             │
│  tax_register (1) ──→ (N) tax_register_entry               │
│    company_id, tax_period_id, register_type,                │
│    register_version, policy_version_id,                     │
│    entry_count, total_amount, is_current                    │
│                                                             │
│  tax_register_entry (1) ──→ (1) tax_explanation            │
│                                 register_entry_id           │
│                                 assignment_id               │
│                                 ledger_line_id              │
│                                 ledger_entry_id             │
│                                 posting_decision_link_id    │
│                                 decision_id                 │
│                                 decision_explanation_id     │
│                                 why_included, why_excluded  │
│                                 rule_code, chain_json       │
└─────────────────────────────────────────────────────────────┘
```

### 9 таблиц в schema `accounting`:

| Таблица | Строк | Назначение |
|---------|-------|-----------|
| `tax_policy` | 6 | Каталог налоговых политик |
| `tax_policy_version` | 6 | Версионированные политики |
| `tax_rule` | 28 | Правила маппинга (account → register) |
| `tax_assignment` | 45 | Связь ledger_line → tax_register |
| `tax_register` | 4 | Иммутабельные регистры (версионные) |
| `tax_register_entry` | 41 | Записи регистров |
| `tax_explanation` | 0 | Цепочка объяснимости (наполняется при explain) |
| `tax_period` | 5 | Налоговые периоды |
| `tax_regime` | 1 | Режимы налогообложения компаний |

---

## 2. Mapping Rules

### Контракт

```
LedgerLine → TaxAssignmentEngine.assign(ledger_line, tax_policy_version)
           → TaxAssignment (register_type, tax_treatment, excluded, reason_code)
           → TaxRegister.generate(assignments, tax_period)
           → TaxRegisterEntry[]
```

**Формула:** `TaxRegister = f(Ledger, TaxPolicyVersion, TaxRegime)`

### Засеянные правила (18 шт., 3 политики)

#### USN_D (УСН Доходы) — 4 правила

| Приоритет | Rule Code | Account | Направление | Регистр | Исключён |
|-----------|-----------|---------|-------------|---------|----------|
| 4 | revenue_to_kudir | 90.01 | credit | KUDIR_INCOME | taxable |
| 3 | cash_receipt_to_kudir | 51 | debit | KUDIR_INCOME | taxable |
| 2 | balance_accounts_excluded | 76 | * | EXCLUDED | excluded |
| 1 | default_exclusion | * | * | EXCLUDED | excluded |

#### USN_DR (УСН Доходы минус Расходы) — 7 правил

| Приоритет | Rule Code | Account | Регистр |
|-----------|-----------|---------|---------|
| 7 | revenue_to_kudir_income | 90.01/credit | KUDIR_INCOME |
| 6 | expense_sales_to_kudir | 44/debit | KUDIR_EXPENSE |
| 5 | expense_general_to_kudir | 26/debit | KUDIR_EXPENSE |
| 4 | supplier_expense | 60/credit | KUDIR_EXPENSE |
| 3 | balance_accounts_excluded | 76/* | EXCLUDED |
| 2 | vat_account_excluded | 68/* | EXCLUDED |
| 1 | default_exclusion | * | EXCLUDED |

#### GENERAL (ОСНО) — 7 правил

| Приоритет | Rule Code | Account | Регистр |
|-----------|-----------|---------|---------|
| 7 | revenue_to_general_income | 90.01/credit | GENERAL_INCOME |
| 6 | vat_sales | 68/credit | VAT_SALES |
| 5 | vat_purchase | 19/debit | VAT_PURCHASE |
| 4 | expense_general | 44/debit | GENERAL_EXPENSE |
| 3 | expense_admin | 26/debit | GENERAL_EXPENSE |
| 2 | balance_accounts_excluded | 76/* | EXCLUDED |
| 1 | default_exclusion | * | EXCLUDED |

### Типы регистров (7)

| Тип | Где используется |
|-----|-----------------|
| `KUDIR_INCOME` | USN_D, USN_DR |
| `KUDIR_EXPENSE` | USN_DR |
| `VAT_SALES` | GENERAL |
| `VAT_PURCHASE` | GENERAL |
| `GENERAL_INCOME` | GENERAL |
| `GENERAL_EXPENSE` | GENERAL |
| `EXCLUDED` | Все режимы (балансовые счета, unmapped) |

---

## 3. API

### Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/tax/policies` | Список политик + версий |
| `GET` | `/api/v1/tax/assignments` | Assignments (фильтры: company, line_id, register_type, is_current) |
| `POST` | `/api/v1/tax/assignments/batch` | Assign all lines для entry |
| `GET` | `/api/v1/tax/registers` | Регистры (фильтры: company, period, type, is_current) |
| `GET` | `/api/v1/tax/registers/{id}` | Регистр + entries |
| `POST` | `/api/v1/tax/registers/generate` | Генерация всех регистров для периода |
| `POST` | `/api/v1/tax/recalculate` | Tax replay (новая policy → новые assignment → новые регистры) |
| `GET` | `/api/v1/tax/periods` | Список налоговых периодов |
| `POST` | `/api/v1/tax/period/close` | Закрытие периода (проверка unassigned lines) |
| `GET` | `/api/v1/tax/explanations` | Объяснение (filter: register_entry_id, register_id, ledger_line_id) |
| `GET` | `/api/v1/tax/metrics` | Агрегированные метрики |
| `POST` | `/api/v1/tax/seed` | Idempotent seed политик |

### Пример запроса: recalculate

```bash
POST /api/v1/tax/recalculate
{
  "company_id": "00000000-0000-0000-0000-000000000001",
  "tax_period_id": "...",
  "tax_policy_version": "2026.01.01"
}
→ {
  "new_assignments_count": 16,
  "superseded_count": 4,
  "registers_created": ["KUDIR_INCOME", "EXCLUDED"],
  "policy_version_used": "2026.01.01",
  "ledger_unchanged": true
}
```

### Пример запроса: explain

```bash
GET /api/v1/tax/explanations?register_entry_id=...
→ {
  "explanations": [{
    "register_entry_id": "...",
    "register_type": "KUDIR_INCOME",
    "tax_treatment": "taxable",
    "excluded": false,
    "why_included": "Account 90.01: no reason",
    "chain": {
      "register_entry": { "account_code": "90.01", "amount": 200000 },
      "ledger_line": { "account_code": "90.01", "direction": "credit" },
      "decision": { "included": true }
    }
  }]
}
```

---

## 4. Policy Versioning Model

```
TaxPolicyVersion
  ├── policy_id         ← TaxPolicy
  ├── version           # "2026.01.01", "2026.07.01"
  ├── effective_from    # Когда вступает в силу
  ├── effective_to      # Когда заменена (NULL = текущая)
  ├── rules_hash        # SHA256(rules) — детерминизм
  ├── rules[]           # TaxRule[]
  └── is_active         # Bool
```

### Инвариант

```
same ledger
+ new tax_policy_version
======================
new tax_registers (ledger не тронут)
```

### Связь с Phase 4 кодом

```
/mcp/server/tools/project_tools.py → domain_context("accounting")
/backend/accounting/tax/
  ├── policy/__init__.py        # TaxPolicy — evaluate(), create_policy_version(), seed_default_policies()
  ├── assignment/__init__.py    # TaxAssignmentEngine — assign(), assign_entry_lines()
  ├── register/__init__.py      # TaxRegister — generate(), save(), generate_all()
  ├── replay/__init__.py        # TaxReplay — recalculate() (НЕ меняет ledger)
  ├── period/__init__.py        # TaxPeriodResolver — find_or_create_period(), close_period()
  ├── explain/__init__.py       # TaxExplainer — explain_register_entry(), explain_register()
  └── api/routes.py             # 12 endpoints
```

---

## 5. E2E Test Results

### 7/7 сценариев

| # | Сценарий | Результат | Доказательство |
|---|----------|-----------|----------------|
| 1 | Tax Assignment Determinism | ✅ | 90.01/credit → KUDIR_INCOME (taxable). 62/debit → EXCLUDED. Одинаковые входы → одинаковый register_type |
| 2 | Exclusion Handling | ✅ | Balance account 62 → EXCLUDED (unmapped_account). Нет правил → нет попадания |
| 3 | Register Generation | ✅ | KUDIR_INCOME: 1 entry, total=150000. Только matched линии |
| 4 | Register Persistence (Immutable) | ✅ | v1, 1 entry, is_current=True. Версионирован |
| 5 | Tax Replay | ✅ | 36 new assignments, ledger_unchanged=True. New policy → new assignments → superseded old |
| 6 | Explainability | ✅ | Chain: 7 звеньев (register_entry → ... → decision_explanation) |
| 7 | Period Management | ✅ | can_close=True. Resolution: USN_D=year, GENERAL=quarter |

### 5/5 Quality Gates

| # | Gate | Результат |
|---|------|-----------|
| QG1 | No duplicate active assignments per ledger_line | ✅ |
| QG2 | Register rebuild consistency (v1 hash == v2 hash) | ✅ |
| QG3 | Replay does NOT change ledger | ✅ (entries до/после равны) |
| QG4 | Policy isolation (USN_DR ≠ GENERAL) | ✅ |
| QG5 | register_v1 ≠ register_v2 (immutable versioning) | ✅ |

---

## 6. Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Ledger_line без assignment при закрытии периода | Средняя | Высокое | `can_close_period()` проверяет unassigned lines |
| Два активных assignment на одну ledger_line | Низкая | Критическое | QG1 проверяет, DB `is_current=true` с unique partial index |
| Replay меняет ledger | Низкая | Критическое | `ledger_unchanged=True` — подтверждено QG3 и E2E #5 |
| Policy version mismatch при генерации регистра | Низкая | Среднее | TaxRegister хранит `policy_version_id` в каждом регистре |
| Loss of explainability после replay | Низкая | Среднее | TaxExplainer работает по assignment, которые superseded исторически сохранены |

---

## 7. Готовность к Phase 5 (Reporting + AI Audit)

### Что Phase 5 получит от Phase 4

```
Phase 4 output:
  TaxRegister (total_amount, register_type, entries, version)
  TaxAssignment (register_type, tax_treatment, reason_code, excluded)
  TaxExplanation chain (до decision_explanation за ≤10 JOIN)
  TaxPolicyVersion (версия, effective_from, rules)
  TaxPeriod (open/closed, resolution)

Phase 5A input:
  TaxRegister.current
  ReportTemplateVersion.active
```

### Границы

| Можно | Нельзя |
|-------|--------|
| `tax_register` читать (current + history) | `ledger_entry` (обход Tax Layer) |
| `tax_register_entry` читать (детализация) | `ledger_line` (нарушает `Report = f(TaxRegister)`) |
| `tax_policy_version` читать | `accounting_decision` (нарушает layer isolation) |
| `tax_period` читать | `accounting_event` (нарушает snapshot-only) |

### Документы freeze

- `docs/accounting/reporting_boundary.md` v3.0.0 — 582 строки, 19 инвариантов
- `docs/accounting/report_ai_boundary.md` v1.1.0 — AIAuditReplay contract
- `docs/adr/ADR-015-report-is-generated-artifact.md` — 9 отклонённых вариантов
- `docs/accounting/roadmap.md` — 5A/5B/6/7 roadmap

### Статус

```
Phase 1–3         ✅ Completed + frozen
Phase 4 (Tax)     ✅ Completed + frozen (E2E=7/7, QG=5/5)
Phase 5A (Report) ❄️ Boundary freeze (v3.0.0)
Phase 5B (AI)     ❄️ Boundary freeze (v1.1.0)
Phase 6 (Signing) 📋 Planned
Phase 7 (Sending) 📋 Planned
```
