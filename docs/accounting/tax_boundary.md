# Phase 4 — Tax Boundary

**Дата:** 2026-06-15
**Статус:** ❄️ **Boundary Freeze** (до реализации)
**Версия:** 1.0.0

---

## 1. Fundamental Formula

```
Tax = f(Ledger, TaxPolicyVersion)
```

NOT:
```
Ledger = f(TaxPolicy)
LedgerLine → tax_register_id (прямая колонка)
```

---

## 2. Архитектурный поток

```
Event → Decision → Posting → Ledger
                                 │
                                 ▼
                          Tax Assignment
                          (TaxAssignmentEngine)
                                 │
                                 ▼
                          Tax Register
                          (TaxRegister.generate())
                                 │
                                 ▼
                          Report → AI Audit
```

### Разрешённые входы в Tax Layer

| Сущность | Режим |
|----------|-------|
| `ledger_line` | Чтение (только current) |
| `ledger_entry.period_id` | Чтение (для определения tax period) |
| `TaxPolicyVersion` | Версия политики |
| `company.tax_regime` | Чтение (через accounting.tax_regime) |

### Запрещённые входы

| Сущность | Причина |
|----------|---------|
| `accounting_event` | Нарушает `Tax = f(Ledger)` |
| `accounting_decision` | Решение уже отражено в проводке |
| `document` | Нарушает snapshot invariant |
| `bank_transaction` | Прямая зависимость от банка |

---

## 3. Почему Ledger не знает про налоги

### Основной принцип

```
Tax = f(Ledger, TaxPolicyVersion)
```

Ledger — факт. Tax — интерпретация факта.

### Аргументы

1. **Независимость политик**: налоговая политика меняется (ставки НДС, лимиты УСН). Ledger не должен перестраиваться при изменении налоговых правил.

2. **Версионирование**: одна проводка → много assignment версий (при смене политики). Если `tax_register_id` хранится в `ledger_line`, каждая смена политики требует UPDATE ledger.

3. **История**: Ledger — immutable. Если налог меняется, история проводок не должна переписываться.

4. **Replay без posting**: пересчёт налога не должен создавать новые проводки.

---

## 4. Выходы Tax Layer

| Сущность | Описание |
|----------|----------|
| `tax_assignment` | Привязка ledger_line к налоговому регистру |
| `tax_register_entry` | Запись в налоговом регистре |
| `tax_register` | Набор записей за период |
| `report_draft` | Черновик отчёта (Phase 5) |

---

## 5. Period Ownership

```
TaxPeriod ≠ AccountingPeriod
```

| Accounting Period | Tax Period |
|-------------------|------------|
| Месяц / квартал | Квартал / год (зависит от режима) |
| OPEN → LOCKED → CLOSED | OPEN → CLOSED |
| Один на компанию | Может агрегировать несколько accounting periods |

**Инвариант:** Многие accounting periods → один tax period.

---

## 6. Replay Tax

```
TaxReplay.recalculate(tax_policy_version)
```

Правила:
- НЕ меняет Ledger
- НЕ меняет Posting
- Создаёт новые assignment (старые superseded)
- Создаёт новые register версии

### Invariant

```
Ledger replay → new postings (immutable old)
Tax replay → new assignments (immutable old)
```

---

## 7. Объяснимость (Explainability)

Каждая запись регистра должна отвечать на вопрос «откуда взялась сумма?».

```
register_entry
  └── tax_assignment
        └── ledger_line
              └── ledger_entry
                    └── posting
                          └── decision (через posting_decision_link)
```

Цепочка восстанавливается без SQL.

---

## 8. Что теперь стабильно (не трогать)

| Компонент | Статус |
|-----------|--------|
| accounting_event | ❄️ Frozen since Phase 1 |
| accounting_decision | ❄️ Frozen since Phase 1 |
| ledger_entry | ❄️ Frozen since Phase 3 |
| ledger_line | ❄️ Frozen (без tax_register_id) |
| period semantics | ❄️ Frozen |
| immutable model | ❄️ Frozen |
| closed period | ❄️ Frozen |

### Что разрешено создавать

- `tax_assignment`
- `tax_register`
- `tax_register_entry`
- TaxPolicyVersion
