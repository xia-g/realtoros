# Phase 3 — Ledger Architectural Freeze

**Дата:** 2026-06-15
**Статус:** ❄️ **ЗАФИКСИРОВАНО — не менять без ADR**

---

## 1. Фундаментальная формула

```
Posting = f(Decision, PostingRulesVersion)
```

- **Decision** ∈ accounting_decision (included = true)
- **PostingRulesVersion** — версия правил разноски на момент проводки
- **f** — PostingEngine, чистая детерминированная функция

НЕ допускается:
```
Posting = f(Event)
Posting = f(Document)
Posting = f(BankTransaction)
Posting = f(CRM)
```

---

## 2. Разрешённые входы

| Сущность | Режим |
|----------|-------|
| `accounting_decision` | Чтение (current + history) |
| `decision_explanation` | Чтение (трассировка) |
| `recognition_snapshot` | Чтение (только metadata) |
| `PostingRulesVersion` | Конфигурация |

Никаких других сущностей.

---

## 3. Immutable Ledger

| Операция | Разрешена | Альтернатива |
|----------|-----------|-------------|
| INSERT ledger_entry | ✅ | — |
| UPDATE ledger_entry | ❌ | Сторно |
| DELETE ledger_entry | ❌ | Сторно |
| SELECT ledger_entry | ✅ | — |

Проводки никогда не изменяются и не удаляются.

---

## 4. Reversal only

Исправление ошибки — только через сторно:

```
Оригинал:         Сторно:              Исправление:
  DR 62  100        DR 90  100           DR 62  120
  CR 90  100        CR 62  100           CR 90  120
```

Каждое сторно содержит `reversed_entry_id` → оригинал.

---

## 5. Closed period invariant

- Закрытый период нельзя repost
- Replay решения в закрытый период → **delta posting** в текущий открытый период
- Delta = new_amount − old_amount
- Только роль `accountant` может снять блокировку периода

---

## 6. Replay semantics

```
Replay в открытом периоде:
  → Новая decision (decision_version+1)
  → PostingEngine создаёт новую проводку
  → Старая проводка immutable
  → Обе видны, current = новая

Replay в закрытом периоде:
  → Новая decision создаётся
  → PostingEngine видит period_lock
  → Создаёт delta posting в ТЕКУЩИЙ открытый период
  → Закрытый период не меняется
```

---

## 7. Запрещённые зависимости

| Связь | Причина |
|-------|---------|
| Ledger → accounting_event | Нарушает `Posting = f(Decision)` |
| Ledger → document | Нарушает snapshot-only invariant |
| Ledger → bank_transaction | Прямая зависимость от банка |
| Ledger → crm_deal | Прямая зависимость от CRM |
| Ledger → внешние API | Непредсказуемость пересчёта |

---

## 8. Posting Rules Versioning

```
Decision ruleset_version:   2026.06.15  (независима)
Posting rules_version:      2026.08.01  (независима)
```

Каждая проводка хранит `posting_rules_version`.
Пересчёт правил разноски не требует пересчёта решения.

---

## 9. Трассировка

```
decision
  └── posting_decision_link
        ├── ledger_entry
        │     └── ledger_line[]
        └── posting_rule (rule_code, version)
```

Для каждой проводки восстанавливается:
- Какое решение её создало
- Какое правило разноски сработало
- Какие счета задействованы
