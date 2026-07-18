# Tax Register Model

**Дата:** 2026-06-15
**Статус:** ❄️ Boundary Freeze
**Версия:** 1.0.0

---

## 1. Контракт

```
TaxRegister.generate(
    assignments: list[TaxAssignment],
    company_id,
    tax_period_id,
    register_type
) → TaxRegisterResult
```

### Результат

```python
@dataclass(frozen=True)
class TaxRegisterEntry:
    entry_id: str
    register_id: str
    assignment_id: str          # → TaxAssignment → ledger_line
    ledger_line_id: str
    account_code: str
    amount: float
    direction: str
    tax_treatment: str
    excluded: bool
    created_at: str

@dataclass(frozen=True)
class TaxRegisterResult:
    register_id: str
    register_type: str          # KUDIR_INCOME | KUDIR_EXPENSE | ...
    company_id: str
    tax_period_id: str
    tax_policy_version: str
    entries: list[TaxRegisterEntry]
    total_amount: float
    version: int
```

---

## 2. Immutable Register

| Операция | Разрешена |
|----------|-----------|
| INSERT tax_register_entry | ✅ |
| UPDATE tax_register_entry | ❌ |
| DELETE tax_register_entry | ❌ |
| SELECT tax_register_entry | ✅ |

Коррекция — только через новую версию регистра (новый `register_version`).

---

## 3. Типы регистров

| Тип | Описание | Налоговый режим |
|-----|----------|-----------------|
| `KUDIR_INCOME` | Книга учёта доходов (УСН) | USN_INCOME, USN_INCOME_EXPENSE |
| `KUDIR_EXPENSE` | Книга учёта расходов (УСН-ДР) | USN_INCOME_EXPENSE |
| `VAT_SALES` | Книга продаж (НДС) | OSNO |
| `VAT_PURCHASE` | Книга покупок (НДС) | OSNO |
| `GENERAL_INCOME` | Регистр доходов (ОСНО) | OSNO |
| `GENERAL_EXPENSE` | Регистр расходов (ОСНО) | OSNO |
| `EXCLUDED` | Необлагаемые операции | Все |

---

## 4. Period Ownership

```
TaxPeriod ≠ AccountingPeriod
```

### Пример

```
Accounting periods (monthly):
  2026-01  OPEN
  2026-02  OPEN
  2026-03  OPEN
  │
  ▼
Tax period (quarterly for USN):
  2026-Q1  OPEN
```

Many accounting periods → one tax period.

### Закрытие

```
Accounting periods CLOSED individually (monthly close).
Tax period CLOSED when all underlying accounting periods are closed.
```

---

## 5. Replay

```
TaxReplay.recalculate(tax_policy_version)
```

1. Загрузить все ledger_line для периода
2. TaxAssignmentEngine.assign() для каждой
3. Создать новые assignment (is_current=true)
4. TaxRegister.generate() для каждого типа
5. Старый регистр остаётся (immutable)

### Пример

```
До replay:
  Register v1: 10 entries, total 1,000,000 RUB
  Policy: 2026.USN.1

После replay:
  Register v1: 10 entries, 1,000,000 RUB (immutable)
  Register v2: 10 entries, 850,000 RUB  (текущий)
  Policy: 2026.USN.2

Ledger: unchanged ✅
```

---

## 6. Explainability

```
tax_register_entry
  │
  ├── assignment_id → TaxAssignment
  │     ├── ledger_line_id → ledger_line
  │     │     └── entry_id → ledger_entry
  │     │           └── batch_id → posting_decision_link
  │     │                 └── decision_id → accounting_decision
  │     │                       └── decision_explanation[]
  │     └── tax_policy_version
  │     └── reason_code
  │
  └── register_type, amount, treatment
```

Каждая сумма в налоговом регистре прослеживается до:
- ledger_line (account, amount, direction)
- accounting_decision (included, reason)
- decision_explanation (rule_code, weight, message)
