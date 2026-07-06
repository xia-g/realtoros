# Posting Model — Ledger Mechanics

**Дата:** 2026-06-15
**Статус:** ❄️ Boundary Freeze
**Версия:** 1.0.0

---

## 1. Фундаментальная формула

```
Posting = f(Decision, PostingRulesVersion)
```

- `Decision` — accounting_decision (included=true)
- `PostingRulesVersion` — версия правил разноски на момент проводки
- `f` — PostingEngine, чистая функция (детерминирована)

### Следствия

- Одно решение → минимум одна проводка
- Одна проводка → минимум две строки (дебет + кредит)
- Сумма дебетов = Сумма кредитов (double-entry invariant)

---

## 2. Сущности

### chart_of_accounts

| Поле | Описание |
|------|----------|
| account_code | VARCHAR(20) — `62`, `90.01`, `51` |
| account_name | Наименование |
| account_type | asset, liability, equity, income, expense |
| is_active | BOOLEAN |
| parent_id | UUID (иерархия) |

### ledger_entry

| Поле | Описание |
|------|----------|
| id | UUID PK |
| company_id | UUID |
| decision_id | UUID → accounting_decision |
| period_id | UUID → tax_period |
| entry_date | DATE |
| description | TEXT |
| is_reversal | BOOLEAN — true, если это сторно |
| reversed_entry_id | UUID → ledger_entry (для сторно) |
| posting_rules_version | VARCHAR(20) |
| created_at | TIMESTAMPTZ |

### ledger_line

| Поле | Описание |
|------|----------|
| id | UUID PK |
| entry_id | UUID → ledger_entry |
| account_code | VARCHAR(20) → chart_of_accounts |
| debit_amount | NUMERIC(16,2) |
| credit_amount | NUMERIC(16,2) |
| amount | NUMERIC(16,2) |
| direction | `debit` / `credit` |

### posting_decision_link

| Поле | Описание |
|------|----------|
| id | UUID PK |
| decision_id | UUID → accounting_decision |
| entry_id | UUID → ledger_entry |
| posting_rule_code | VARCHAR(50) |
| posting_rule_version | VARCHAR(20) |

---

## 3. Immutable Accounting

### Запрещено

```sql
-- ❌ НИКОГДА
UPDATE ledger_entry SET amount = 100 WHERE id = '...';
DELETE FROM ledger_line WHERE entry_id = '...';
UPDATE ledger_entry SET is_reversal = false WHERE id = '...';
```

### Разрешено

```sql
-- ✅ Сторно (reversal)
INSERT INTO ledger_entry (..., is_reversal=true, reversed_entry_id='original_id')
VALUES (...);

INSERT INTO ledger_line (entry_id, account_code, amount, direction) VALUES
  ('new_entry', '62', 100, 'debit'),
  ('new_entry', '90', 100, 'credit');

-- ✅ Новая проводка (исправленная)
INSERT INTO ledger_entry (...) VALUES (...);
INSERT INTO ledger_line (...) VALUES (120, 'debit'), (120, 'credit');
```

---

## 4. Reversal Strategy

### Полное сторно (full reversal)

```
Оригинал:
  DR 62    100
  CR 90    100

Сторно (is_reversal=true, reversed_entry_id=original):
  DR 90    100
  CR 62    100

Исправление:
  DR 62    120
  CR 90    120

Итоговый эффект:
  DR 62:   -100 + 120 = 20
  CR 90:   -100 + 120 = 20
```

### Когда используется
- Ошибка в сумме
- Ошибка в счете
- Отмена решения (decision_state → EXCLUDED)

---

## 5. Period Lock

### Статусы периода

```
OPEN    → можно создавать проводки
LOCKED  → нельзя создавать проводки (можно сторнировать)
CLOSED  → нельзя ничего
```

### Поведение при replay в закрытый период

```
1. Decision создаётся (decision_version+1)
2. PostingEngine проверяет period_lock для даты решения
3. Период CLOSED → delta posting:
   новая_проводка.period_id = ТЕКУЩИЙ_ОТКРЫТЫЙ_ПЕРИОД
   новая_проводка.description = "Correction for period 2026.Q1"
   ledger_line.amount = new_amount - old_amount
4. Закрытый период НЕ ТРОГАЕТСЯ
```

### Снятие блокировки

- Только роль `accountant` или `admin`
- Обязательно логирование (actor_id, reason)
- После снятия → replay возможен в этот период

---

## 6. Invariants (current + future)

### Current (Phase 3 — enforced)

| # | Invariant | Где |
|---|-----------|-----|
| 1 | `Σ debit = Σ credit` | PostingEngine.validate() |
| 2 | Every ledger_line belongs to exactly one tax period | `period_id NOT NULL` |
| 3 | No UPDATE/DELETE on ledger_entry | Reversal only |
| 4 | No self-reversal | `ck_no_self_reversal` |
| 5 | manual_adjustment requires `decision_state = 'review_required'` + `reason_code` | ManualAdjustment.generate() |

### Future (Phase 4 — Tax Registers)

| # | Invariant | Значение |
|---|-----------|----------|
| 6 | **Every ledger_line belongs to exactly one tax register or explicitly excluded** | `tax_register_id NOT NULL` OR `excluded_from_tax = true` |

Запрещено состояние: `ledger exists, tax state unknown`.

Каждая проводка должна быть маппирована в:
- КУДиР (доходы / расходы)
- Книгу продаж (НДС)
- Книгу покупок (НДС)
- Регистр доходов (УСН / ОСНО)
- Регистр расходов (УСН / ОСНО)
- Explicit exclusion (не облагается)

---

## 7. Пример: полный lifecycle

```
Событие: sale, 150 000 RUB
  │
  ▼
Decision: INCLUDED (has_supporting_document ✅, amount_threshold ✅)
  │
  ▼
PostingEngine.evaluate(decision, posting_rules_version="2026.08.01")
  │
  ├── Rule: revenue_recognition (priority 100)
  │     DR 62 "Расчёты с покупателями"    150 000
  │     CR 90.01 "Выручка"                150 000
  │
  ├── Rule: vat_accrual (priority 80)
  │     DR 90.03 "НДС"                     30 000
  │     CR 68 "НДС к уплате"              30 000
  │
  └── Validate: SUM(debit) = SUM(credit) = 180 000 ✅
  │
  ▼
ledger_entry (id, company_id, decision_id, period_id, date, "Sale #123")
  ├── ledger_line (account=62,     debit=150000,  credit=0)
  ├── ledger_line (account=90.01,  debit=0,       credit=150000)
  ├── ledger_line (account=90.03,  debit=30000,   credit=0)
  └── ledger_line (account=68,     debit=0,       credit=30000)
```
