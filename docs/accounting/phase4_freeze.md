# Phase 4 — Tax Assignment + Registers Freeze

**Дата:** 2026-06-15
**Статус:** ❄️ **ЗАФИКСИРОВАНО — не менять без ADR**

---

## 1. Фундаментальная формула

```
Tax = f(Ledger, TaxPolicyVersion)
```

НЕ: `LedgerLine → tax_register_id`

---

## 2. Стабильно (не трогать)

### Сущности Phase 1–3 (frozen)

| Сущность | С | Статус |
|----------|---|--------|
| accounting_event | P1 | ❄️ |
| accounting_batch | P1 | ❄️ |
| accounting_decision | P1 | ❄️ |
| decision_explanation | P2 | ❄️ |
| recognition_snapshot | P2 | ❄️ |
| ledger_entry | P3 | ❄️ |
| ledger_line | P3 | ❄️ (без tax_register_id) |
| posting_batch | P3 | ❄️ |
| tax_period | P1 | ❄️ |
| tax_regime | P1 | ❄️ |

### Инварианты (frozen)

| # | Инвариант | С |
|---|-----------|---|
| 1 | `Decision = f(Event, Snapshot, RulesetVersion)` | P1 |
| 2 | `Posting = f(Decision, PostingRulesVersion)` | P3 |
| 3 | `Σ debit = Σ credit` | P3 |
| 4 | Every ledger_line belongs to exactly one tax period | P3 |
| 5 | No UPDATE/DELETE on ledger | P3 |
| 6 | closed period cannot be reposted | P3 |

---

## 3. Что разрешено менять при реализации

| Компонент | Можно менять |
|-----------|-------------|
| TaxAssignment rules | ✏️ имплементация |
| TaxPolicyVersion | ✏️ версионирование |
| TaxRegister types | ✏️ добавление типов |
| Assignment → Register mapping | ✏️ правила маппинга |
| API endpoints | ✏️ интерфейс |
| Explainability queries | ✏️ отчёты |

---

## 4. Запрещено

| Действие | Причина |
|----------|---------|
| Добавить `tax_register_id` в `ledger_line` | Нарушает `Tax = f(Ledger)`. Ledger immutable. |
| UPDATE ledger_line после posting | Immutable violation |
| Прямая зависимость Tax → Decision (минуя Ledger) | Обход immutable layer |
| Tax assignment в той же транзакции, что и posting | Разделение ответственности |

---

## 5. Критерии начала реализации

- [x] Tax boundary document exists
- [x] Tax assignment model documented
- [x] Tax register model documented
- [x] ADR-014 written
- [ ] Data gate: assignment воспроизводим (same inputs → same result)
- [ ] Data gate: replay не меняет ledger
- [ ] Performance gate: 10k assignments < 1 min
- [ ] Operations gate: tax replay возможен без даунтайма

---

## 6. Что будет в Phase 4

| Модуль | Описание |
|--------|----------|
| TaxAssignmentEngine | assign(ledger_line, tax_policy_version) → TaxAssignment |
| TaxRegister | generate(assignments, period) → register_entries |
| TaxReplay | recalculate(tax_policy_version) |
| API | GET assignments, GET register, POST replay |
| Observability | assignment metrics, register reconciliation |
| Quality gates | determinism, idempotency, period lock |
