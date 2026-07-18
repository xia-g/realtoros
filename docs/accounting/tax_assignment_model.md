# Tax Assignment Model

**Дата:** 2026-06-15
**Статус:** ❄️ Boundary Freeze
**Версия:** 1.0.0

---

## 1. Контракт

```
TaxAssignmentEngine.assign(
    ledger_line,
    company_id,
    period_id,
    tax_policy_version
) → TaxAssignment
```

- **ledger_line** — одна строка проводки (account, amount, direction)
- **company_id** — для определения tax_regime
- **period_id** — для определения tax_period
- **tax_policy_version** — версия налоговой политики

### Результат

```python
@dataclass(frozen=True)
class TaxAssignment:
    assignment_id: str
    ledger_line_id: str
    tax_policy_version: str
    tax_register_type: str       # KUDIR_INCOME | KUDIR_EXPENSE | VAT_SALES | ...
    tax_treatment: str           # taxable | deductible | exempt | excluded
    excluded: bool               # True = явное исключение из налогов
    reason_code: str | None      # почему excluded или почему именно этот регистр
    is_current: bool = True
```

---

## 2. НЕ изменяет ledger

```
TaxAssignment НЕ пишет в:
  ❌ ledger_line.tax_register_id
  ❌ ledger_line.excluded_from_tax
  ❌ ledger_entry.tax_status
```

Ledger — immutable. Налоговая интерпретация — отдельная сущность.

---

## 3. Версионирование

Одна ledger_line → много TaxAssignment версий:

```
assignment_id | ledger_line_id | version | is_current | tax_policy_version
──────┰───────┼────────┰───────┼─────────┼─────────┰───┼──────────────────
uuid 1 │ line A       │ v1     │ false    │ 2026.USN.1
uuid 2 │ line A       │ v2     │ true     │ 2026.USN.2  ← новая политика
```

### Инвариант

```
One ledger_line
→ many assignment versions
→ exactly ONE active (is_current = true)
```

---

## 4. Режимы и маппинг

### USN_INCOME (УСН «Доходы»)

| Ledger account | Amount direction | Tax register | Treatment |
|---------------|-----------------|--------------|-----------|
| 90.01 (Выручка) | credit | KUDIR_INCOME | taxable |
| 51 (Расчётный счёт) | debit | KUDIR_INCOME | taxable |
| Все остальные | — | EXCLUDED | excluded |

### USN_INCOME_EXPENSE (УСН «Доходы минус Расходы»)

| Ledger account | Direction | Tax register | Treatment |
|---------------|-----------|--------------|-----------|
| 90.01 (Выручка) | credit | KUDIR_INCOME | taxable |
| 44 (Расходы на продажу) | debit | KUDIR_EXPENSE | deductible |
| 60 (Поставщики) | credit | KUDIR_EXPENSE | deductible |
| 26 (Общехозяйственные) | debit | KUDIR_EXPENSE | deductible |

### OSNO (ОСНО)

| Ledger account | Direction | Tax register |
|---------------|-----------|--------------|
| 90.01 (Выручка) | credit | GENERAL_INCOME |
| 68 (НДС) | credit | VAT_SALES |
| 19 (НДС по приобретённым) | debit | VAT_PURCHASE |
| 44 (Расходы) | debit | GENERAL_EXPENSE |

---

## 5. Правила маршрутизации

```
input(ledger_line, company, period)
  │
  ├── account_code in INCOME_ACCOUNTS
  │     → KUDIR_INCOME / GENERAL_INCOME
  │
  ├── account_code in EXPENSE_ACCOUNTS
  │     → KUDIR_EXPENSE / GENERAL_EXPENSE
  │
  ├── account_code in VAT_ACCOUNTS
  │     → VAT_SALES / VAT_PURCHASE
  │
  ├── account_code in EXCLUDED_ACCOUNTS
  │     → excluded (reason_code = "balance_account")
  │
  └── otherwise
        → excluded (reason_code = "unmapped_account")
```

---

## 6. Replay Tax

```
TaxReplay.recalculate(tax_policy_version)
```

- НЕ меняет ledger
- Создаёт новые TaxAssignment (is_current=true)
- Старые assignment помечаются is_current=false
- TaxRegister перегенерируется

### Коррекция ошибки

```
Было: amount=100000 → KUDIR_INCOME (налоговая база 100000)
Стало: новая политика → KUDIR_INCOME (налоговая база 85000)

Шаг 1: TaxReplay.recalculate("2026.USN.2")
Шаг 2: Новые assignment созданы
Шаг 3: Новые register entries созданы
Шаг 4: Ledger не тронут ✅
```
