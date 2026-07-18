# Phase 3 — Ledger Boundary

**Дата:** 2026-06-15
**Статус:** ❄️ **Boundary Freeze** (до реализации)
**Версия:** 1.0.0

---

## 1. Единственный вход в Ledger

```
accounting_decision
    │
    ▼
  Posting Engine
    │
    ▼
  ledger_entry + ledger_line

Формула: Posting = f(Decision, PostingRulesVersion)
```

### Разрешённые входы

| Сущность | Режим доступа |
|----------|---------------|
| `accounting_decision` | Чтение (current + history) |
| `decision_explanation` | Чтение (для трассировки) |
| `recognition_snapshot` | Чтение (только metadata) |
| `PostingRulesVersion` | Версия правил на момент разноски |

### Запрещённые входы

| Сущность | Причина |
|----------|---------|
| `accounting_event` | Нарушает формулу `Posting = f(Decision)` |
| `document` | Нарушает snapshot-only invariant |
| `bank_transaction` | Прямая зависимость от банка |
| `crm_deal` | Прямая зависимость от CRM |
| Внешние API | Непредсказуемость пересчёта |

---

## 2. Выходы

| Сущность | Описание |
|----------|----------|
| `chart_of_accounts` | План счетов (системный справочник) |
| `ledger_entry` | Заголовок проводки (period, date, description) |
| `ledger_line` | Строка проводки (account, debit, credit, amount) |
| `posting_decision_link` | Связь проводки → решение (трассировка) |
| `period_lock` | Блокировка закрытых периодов |

---

## 3. Архитектурный поток

```
accounting_decision (решение: INCLUDED)
    │
    ▼
PostingEngine.evaluate(decision, posting_rules_version)
    │
    ├── Load posting_rules for this company/tax_regime
    ├── Match decision → chart_of_accounts entries
    ├── Generate ledger_entry + ledger_line[]
    ├── Validate: SUM(debit) = SUM(credit)
    └── Save (immutable)
    │
    ▼
ledger_entry + ledger_line[]
```

### Трассировочная связь

```
decision
  └── posting_decision_link
        ├── ledger_entry
        │     └── ledger_line[]
        └── posting_rule (какое правило сработало)
```

---

## 4. Replay semantics

```
Replay в незакрытом периоде:
─────────────────────────────
1. Новая decision создаётся (decision_version+1)
2. PostingEngine создаёт НОВУЮ проводку
3. Старая проводка НЕ удаляется (immutable)
4. Обе проводки видны, current = новая

Replay в закрытом периоде:
───────────────────────────
1. Новая decision создаётся
2. PostingEngine видит period_lock → создаёт delta posting
3. Delta = new_amount - old_amount
4. Delta попадает в ТЕКУЩИЙ открытый период
5. Закрытый период не меняется
```

---

## 5. Immutable ledger

| Операция | Разрешена | Альтернатива |
|----------|-----------|-------------|
| `INSERT` ledger_entry | ✅ | — |
| `UPDATE` ledger_entry | ❌ | Сторно (reversal) |
| `DELETE` ledger_entry | ❌ | Сторно |
| `SELECT` ledger_entry | ✅ | — |

---

## 6. Коррекция ошибок

```
Ошибка: неправильная сумма 100 → 120

Шаг 1: Сторно
  DR 62    100
  CR 90    100

Шаг 2: Новая проводка
  DR 62    120
  CR 90    120

Итог: 3 проводки, баланс 0
```

---

## 7. Закрытие периода

```
period_lock:
  period_id
  locked_at
  locked_by
  reason
  is_closed (bool)
```

- Закрытый период не даёт создать проводку
- Replay в закрытый период → delta posting в открытый
- Только роль `accountant` может снять блокировку

---

## 8. Posting Rules Versioning

```
ruleset_version (Decision Engine): 2026.06.15
posting_rules_version (Posting Engine): 2026.08.01
```

- Версии независимы
- Пересчёт правил разноски не требует пересчёта решения
- Каждая проводка хранит `posting_rules_version`

---

## 9. Explainability (трассировка)

```
decision (id, included, reason)
  └── posting_decision_link
        ├── ledger_entry (id, date, description)
        │     ├── ledger_line (account 62, debit, 100)
        │     └── ledger_line (account 90, credit, 100)
        └── posting_rule (rule_code: "revenue_recognition", version: "2026.08")
```

Для каждой проводки восстанавливается:
- Какое решение её создало
- Какое правило разноски сработало
- Какие счета задействованы
