# Epic 2 / Stream 2 — Ledger & Posting Engine Proposal

```
Epic              2 — Accounting Engine
Stream            2 — Ledger & Posting Engine
Architecture      v3.0 (Platform FROZEN)
────────────────────────────────────────────────────
Status            PROPOSED (Phase 0)
```

## 1. Executive Summary

Stream 1 создал доменную модель и document→entry mapping.
Stream 2 строит финансовую машину вокруг этих записей:

```
Entry → Journal → Ledger → Balances → Reporting Foundation
```

Stream 1 был: "как создать бухгалтерскую запись из документа".
Stream 2 будет: "как управлять финансовым состоянием".

Никаких изменений в Platform или Knowledge Layer.

## 2. Current State (после Stream 1)

```
Document → AccountingEntry (DRAFT) → VALIDATED → POSTED

POSTED entry:
  • записана в таблицу accounting_entries
  • debit = credit проверен
  • линии записаны в entry_lines
  • статус = POSTED
```

**Чего не хватает:**

- Нет явного Journal (лог операций)
- Нет Ledger (обороты по счетам)
- Нет Period management (открытие/закрытие)
- Нет Balance computation
- Нет Reporting queries (ОСВ, оборотка)

## 3. Stream 2 Domain Model

### 3.1 Journal (расширение)

```python
@dataclass
class JournalEntry:
    """Запись в журнале — одна проводка."""
    journal_entry_id: str
    journal_id: str
    entry_id: str              # ссылка на AccountingEntry
    posting_date: date
    period_id: str
    sequence_number: int       # порядковый номер в журнале
    created_at: datetime
```

### 3.2 Ledger (оборотная ведомость по счёту)

```python
@dataclass
class LedgerEntry:
    """Движение по счёту (одна строка ledger)."""
    ledger_entry_id: str
    account_id: str
    entry_id: str
    period_id: str
    posting_date: date
    debit: Decimal
    credit: Decimal
    balance_after: Decimal      # сальдо после проводки
    description: str
```

### 3.3 Period (управление периодами)

```python
PERIOD_TRANSITIONS = {
    "OPEN": ["CLOSING", "LOCKED"],
    "CLOSING": ["CLOSED", "OPEN"],
    "CLOSED": ["LOCKED"],
    "LOCKED": [],
}
```

### 3.4 Account Balance

```python
@dataclass
class AccountBalance:
    account_id: str
    period_id: str
    opening_debit: Decimal
    opening_credit: Decimal
    turnover_debit: Decimal
    turnover_credit: Decimal
    closing_debit: Decimal
    closing_credit: Decimal
```

## 4. Ledger Engine

### 4.1 Posting Service

```python
class PostingService:
    """Post an entry to the ledger.

    When entry.status → POSTED:
      1. Calculate sequence number in journal
      2. Create JournalEntry record
      3. For each EntryLine, create LedgerEntry with running balance
      4. Update account balances for the period
    """

    def post_entry(self, entry_id: str) -> str | None:
        """Post entry. Returns error or None."""
        entry = repo.get_entry(entry_id)
        if entry.status != "VALIDATED":
            return "Only VALIDATED entries can be posted"
        if not entry.is_balanced:
            return "Entry not balanced"

        # Atomic posting
        with transaction():
            seq = self._next_sequence(entry.period_id)
            journal_entry = JournalEntry(...)
            repo.save_journal_entry(journal_entry)

            for line in entry.lines:
                balance = self._compute_balance(line.account_id, entry.period_id)
                ledger_entry = LedgerEntry(
                    account_id=line.account_id,
                    debit=line.debit,
                    credit=line.credit,
                    balance_after=balance + line.debit - line.credit,
                )
                repo.save_ledger_entry(ledger_entry)
                repo.update_account_balance(line.account_id, entry.period_id,
                                            line.debit, line.credit)

        repo.update_entry_status(entry_id, "POSTED")
```

### 4.2 Balance Computation

```python
def compute_closing_balance(account: Account,
                            period: AccountingPeriod) -> AccountBalance:
    """Compute opening + turnover = closing for an account."""
    turnover = repo.get_account_turnover(account.account_id, period.period_id)

    # Opening balance = closing of previous period
    opening = repo.get_opening_balance(account.account_id, period.period_id)

    # For asset/expense accounts: closing = opening_debit + turnover_debit - turnover_credit
    # For liability/revenue/equity: closing = opening_credit + turnover_credit - turnover_debit
    if account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
        closing_debit = max(0, opening.debit - opening.credit + turnover["debit"] - turnover["credit"])
        closing_credit = max(0, - (opening.debit - opening.credit + turnover["debit"] - turnover["credit"]))
    else:
        closing_credit = max(0, opening.credit - opening.debit + turnover["credit"] - turnover["debit"])
        closing_debit = max(0, - (opening.credit - opening.debit + turnover["credit"] - turnover["debit"]))

    return AccountBalance(...)
```

## 5. New Tables

### 5.1 journal_entries

```sql
CREATE TABLE journal_entries (
    journal_entry_id    TEXT PRIMARY KEY,
    journal_id          TEXT NOT NULL,
    entry_id            TEXT NOT NULL REFERENCES accounting_entries(entry_id),
    posting_date        DATE NOT NULL,
    period_id           TEXT NOT NULL,
    sequence_number     INTEGER NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.2 ledger_entries

```sql
CREATE TABLE ledger_entries (
    ledger_entry_id     TEXT PRIMARY KEY,
    account_id          TEXT NOT NULL REFERENCES accounts(account_id),
    entry_id            TEXT NOT NULL REFERENCES accounting_entries(entry_id),
    period_id           TEXT NOT NULL,
    posting_date        DATE NOT NULL,
    debit               NUMERIC(18,2) NOT NULL DEFAULT 0,
    credit              NUMERIC(18,2) NOT NULL DEFAULT 0,
    balance_after       NUMERIC(18,2) NOT NULL DEFAULT 0,
    description         TEXT NOT NULL DEFAULT ''
);
```

### 5.3 account_balances

```sql
CREATE TABLE account_balances (
    account_id          TEXT NOT NULL,
    period_id           TEXT NOT NULL,
    opening_debit       NUMERIC(18,2) NOT NULL DEFAULT 0,
    opening_credit      NUMERIC(18,2) NOT NULL DEFAULT 0,
    turnover_debit      NUMERIC(18,2) NOT NULL DEFAULT 0,
    turnover_credit     NUMERIC(18,2) NOT NULL DEFAULT 0,
    closing_debit       NUMERIC(18,2) NOT NULL DEFAULT 0,
    closing_credit      NUMERIC(18,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, period_id)
);
```

## 6. API Contracts (новые)

### 6.1 Posting

```
POST /api/v1/accounting/entries/{id}/post      — уже существует
  → теперь также создаёт JournalEntry + LedgerEntry
```

### 6.2 Ledger queries

```
GET  /api/v1/accounting/ledger/{account_id}     — уже существует
  → теперь с balances и running totals

GET  /api/v1/accounting/ledger/{account_id}/entries
  → список движений по счёту с балансом после каждой
```

### 6.3 Period management

```
POST /api/v1/accounting/periods/{id}/close      — закрыть период
POST /api/v1/accounting/periods/{id}/open       — открыть повторно
GET  /api/v1/accounting/periods                 — список периодов
POST /api/v1/accounting/periods                 — создать период
```

### 6.4 Balance & Reporting

```
GET  /api/v1/accounting/balance-sheet           — баланс (активы / пассивы)
GET  /api/v1/accounting/profit-loss             — P&L (доходы / расходы)
GET  /api/v1/accounting/trial-balance           — уже существует
```

## 7. Test Strategy

### 7.1 Unit Tests

```
✓ Posting creates JournalEntry
✓ Posting creates LedgerEntry for each line
✓ LedgerEntry has correct balance_after
✓ Account balance updated after posting
✓ Period close blocks new entries
✓ Period open after close allowed
✓ Balance computation correct for asset accounts
✓ Balance computation correct for liability accounts
```

### 7.2 Integration Tests

```
✓ Full flow: DRAFT → VALIDATED → POSTED → ledger updated
✓ Journal sequence numbers are sequential
✓ Ledger entries ordered by posting date
✓ Running balance correct after multiple postings
✓ Period close blocks further postings
✓ Opening balance = previous period's closing
```

### 7.3 Regression

```
✓ All 1182 existing tests pass
✓ Platform unchanged
```

## 8. Implementation Order

### T1 — Journal + Ledger Tables

```
Tables:
  journal_entries, ledger_entries, account_balances

Deliverable:
  New tables created
  Existing post endpoint writes to journal + ledger
```

### T2 — Posting Service

```
Files:
  backend/services/accounting/posting.py

Deliverable:
  Journal sequence numbering
  Ledger entries with running balance
  Account balance updates (atomic)
```

### T3 — Period Management

```
Files:
  backend/services/accounting/periods.py

Deliverable:
  Period lifecycle (OPEN → CLOSING → CLOSED → LOCKED)
  Posting blocked in closed periods
```

### T4 — Balance Computation

```
Files:
  backend/services/accounting/ledger.py (расширение)

Deliverable:
  Opening balance from previous period
  Closing balance computation
  Balance sheet query
  P&L query
```

### T5 — API + Integration Tests

```
Files:
  backend/api/routes/accounting.py (расширение)
  backend/tests/integration/test_accounting_ledger.py

Deliverable:
  Period management endpoints
  Ledger detail endpoint
  Balance sheet + P&L endpoints
  Full integration tests
```

## 9. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Period boundary violations | Entries in wrong period | Strict period check on post |
| Balance computation errors | Wrong financial state | Double-check with separate aggregation |
| Sequence gaps on failure | Missing journal numbers | Use sequence table with locking |
| Posting in closed period | Financial state corrupted | Block all mutations in closed periods |

## 10. Architectural Invariants

```
1. Platform frozen            — 0 changes
2. Knowledge immutable        — unchanged
3. POSTED entry = immutable   — no reversal, only new corrective entry
4. Journal is append-only     — no deletion of journal entries
5. Ledger is append-only      — no deletion of ledger entries
6. Balance = computed         — not stored independently in v1
```

## 11. GO / NO-GO Criteria

**GO** if:
1. ✅ Ledger can be built on existing accounting_entries + entry_lines
2. ✅ Platform remains frozen (0 changes)
3. ✅ Posting is transactional (all-or-nothing)
4. ✅ Period boundaries are enforceable

**NO-GO** if:
1. ❌ Requires Platform component change
2. ❌ Requires Knowledge Layer modification
3. ❌ Requires AI for posting logic

```
Phase 0 verdict:

  Product Layer:    ✅ Ledger Engine + Period Management + Balance Computation
  Platform changes: 0 (predicted)
  Knowledge changes: 0
  GO recommendation: ✅ STRONG GO
```
