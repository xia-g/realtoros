# Epic 2 / Stream 3 — Reporting & Reconciliation Foundation Proposal

```
Epic              2 — Accounting Engine
Stream            3 — Reporting & Reconciliation Foundation
Architecture      v3.0 (Platform FROZEN)
────────────────────────────────────────────────────
Status            PROPOSED (Phase 0)
```

## 1. Executive Summary

Stream 1 создал доменную модель и document→entry mapping.
Stream 2 построил Journal + Ledger + Posting Engine.
Stream 3 делает финансовое состояние **видимым и проверяемым**.

Три направления:
1. **Trial Balance** — оборотно-сальдовая ведомость (уже существует)
2. **Financial Reports** — Balance Sheet, P&L (уже существуют, нужна доработка)
3. **Reconciliation** — сверка банковских выписок с ledger

Никаких изменений в Platform или Knowledge Layer.

## 2. Current State (после Stream 2)

```
Entry → Journal → Ledger → Account Balances → Trial Balance
                                                 ↓
                                          Balance Sheet ✅
                                          P&L ✅
```

**Что уже есть:**
- Trial balance (GET /accounting/trial-balance)
- Balance sheet (GET /accounting/balance-sheet)
- Profit & Loss (GET /accounting/profit-loss)
- Journal (GET /accounting/journal)
- Ledger detail (GET /accounting/ledger/{id}/entries)

**Чего не хватает:**
- Отчёты без дублирования данных (сводные, по периодам)
- Reconciliation (bank statement ↔ cash ledger)
- Period closing workflow (автоматический)
- Report exports (CSV, Excel)
- Dashboard data endpoint

## 3. Stream 3 Domain Model

### 3.1 Reconciliation

```python
@dataclass
class ReconciliationRun:
    """Одна сверка — bank statement против cash ledger."""
    run_id: str
    period_id: str
    account_id: str          # cash account (51)
    statement_balance: Decimal
    ledger_balance: Decimal
    difference: Decimal
    status: str              # "PENDING" | "MATCHED" | "UNMATCHED" | "RESOLVED"
    created_at: datetime
    resolved_at: datetime | None

@dataclass
class ReconciliationLine:
    """Строка сверки — одна транзакция."""
    line_id: str
    run_id: str
    transaction_date: date
    amount: Decimal
    description: str
    matched: bool
    match_type: str          # "ledger" | "statement" | "unmatched"
    match_ref: str | None    # ссылка на ledger_entry_id или bank_line_id
```

### 3.2 Report Definition

```python
@dataclass
class ReportDefinition:
    """Определение отчёта (структура, не данные)."""
    report_id: str
    name: str
    report_type: str         # "balance_sheet" | "profit_loss" | "trial_balance"
    period_id: str
    sections: list[ReportSection]

@dataclass
class ReportSection:
    section_id: str
    name: str
    account_type_filter: str  # "asset" | "liability" | "expense" | ...
    accounts: list[dict]      # account + balance
    total: Decimal
```

### 3.3 Period Closing

```python
PERIOD_CLOSING_STEPS = [
    "verify_trial_balance",      # check debit = credit
    "compute_depreciation",      # future
    "close_revenue_accounts",    # transfer P&L to retained earnings
    "lock_period",               # no more changes
]

class PeriodCloser:
    """Execute period closing steps in order."""

    def close(self, period_id: str) -> list[str]:
        steps_log = []
        # 1. Verify TB
        tb = repo.get_trial_balance(period_id)
        if not self._is_balanced(tb):
            raise ClosingError("Trial balance not balanced")
        steps_log.append("Trial balance verified")

        # 2. Compute closing balances
        svc.compute_closing_balances(period_id)
        steps_log.append("Closing balances computed")

        # 3. Close revenue/expense accounts → retained earnings
        self._close_nominal_accounts(period_id)
        steps_log.append("Nominal accounts closed")

        # 4. Lock period
        svc.transition_period(period_id, "CLOSED")
        steps_log.append("Period locked")

        return steps_log
```

## 4. New Tables

### 4.1 reconciliation_runs

```sql
CREATE TABLE reconciliation_runs (
    run_id              TEXT PRIMARY KEY,
    period_id           TEXT NOT NULL,
    account_id          TEXT NOT NULL,
    statement_balance   NUMERIC(18,2) NOT NULL DEFAULT 0,
    ledger_balance      NUMERIC(18,2) NOT NULL DEFAULT 0,
    difference          NUMERIC(18,2) NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMP
);
```

### 4.2 reconciliation_lines

```sql
CREATE TABLE reconciliation_lines (
    line_id             TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES reconciliation_runs(run_id),
    transaction_date    DATE NOT NULL,
    amount              NUMERIC(18,2) NOT NULL DEFAULT 0,
    description         TEXT NOT NULL DEFAULT '',
    matched             BOOLEAN NOT NULL DEFAULT FALSE,
    match_type          TEXT NOT NULL DEFAULT '',
    match_ref           TEXT
);
```

### 4.3 period_close_log

```sql
CREATE TABLE period_close_log (
    log_id              TEXT PRIMARY KEY,
    period_id           TEXT NOT NULL,
    step_name           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'OK',
    details             TEXT,
    executed_at         TIMESTAMP NOT NULL DEFAULT NOW()
);
```

## 5. API Contracts

### 5.1 Reporting (улучшение существующего)

```
GET /accounting/trial-balance         — улучшить: totals, period comparison
GET /accounting/balance-sheet         — улучшить: totals, sections
GET /accounting/profit-loss           — улучшить: totals, net profit
```

### 5.2 Reconciliation

```
POST /accounting/reconciliation/start
  → создать сверку для cash account, вернуть unmatched lines

POST /accounting/reconciliation/{run_id}/match
  body: { "line_id": "...", "match_ref": "..." }
  → отметить строку как matched

GET  /accounting/reconciliation/{run_id}
  → статус сверки + matched/unmatched

POST /accounting/reconciliation/{run_id}/resolve
  → подтвердить сверку
```

### 5.3 Period Close

```
POST /accounting/periods/{id}/close        — улучшить: multi-step close
GET  /accounting/periods/{id}/close-log    — история закрытия
```

## 6. Implementation Order

### T1 — Reporting improvements

```
Files:
  backend/services/accounting/reporting.py
  backend/api/routes/accounting.py (extension)

Deliverable:
  Trial balance with period totals
  Balance sheet with asset/liability totals
  P&L with net profit computation
```

### T2 — Reconciliation

```
Files:
  backend/services/accounting/reconciliation.py
  backend/api/routes/reconciliation.py

Deliverable:
  Start reconciliation run
  Match lines
  Resolve reconciliation
```

### T3 — Period close workflow

```
Files:
  backend/services/accounting/closing.py

Deliverable:
  Multi-step period closing
  Close log
  Nominal account closing
```

### T4 — Integration tests

```
Files:
  backend/tests/integration/test_accounting_reporting.py

Deliverable:
  Full reporting flow
  Reconciliation flow
  Period close flow
```

## 7. Architectural Invariants

```
1. Platform frozen           — 0 changes
2. Reports = computed        — not stored separately
3. Reconciliation = additive — doesn't modify ledger
4. Period closing = ordered  — steps cannot be skipped
5. No AI in v1               — rule-based reconciliation
```

## 8. GO / NO-GO Criteria

**GO** if:
1. ✅ Reporting can be built on existing ledger data
2. ✅ Platform remains frozen
3. ✅ Reconciliation is rule-based (not AI)
4. ✅ Period closing is ordered and auditable

**NO-GO** if:
1. ❌ Requires Platform component change
2. ❌ Requires Knowledge Layer modification
3. ❌ Requires AI for reconciliation

```
Phase 0 verdict:

  Product Layer:    ✅ Reporting + Reconciliation + Period Close
  Platform changes: 0 (predicted)
  Knowledge changes: 0
  GO recommendation: ✅ STRONG GO
```
