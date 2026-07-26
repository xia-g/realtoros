# Epic 2 / Stream 1 — Accounting Domain Model Proposal

```
Epic              2 — Accounting Engine
Stream            1 — Accounting Core Domain
Architecture      v3.0 (Platform FROZEN)
Knowledge Layer   v3.0 (immutable)
────────────────────────────────────────────────────
Status            PROPOSED (Phase 0)
```

## 1. Executive Summary

После Epic 1 система умеет проводить документ от загрузки до routing решения.
Accounting — первый production consumer этого pipeline.

Stream 1 создаёт **доменный язык бухгалтерии**:
Account, Journal, Entry, Transaction, Period.

Без UI, без отчётов, без AI.
Только модель.

Accounting — Product Layer. Никаких изменений в Platform или Knowledge.

## 2. Accounting vs Knowledge Boundary

```
Knowledge answers:    "Откуда мы это знаем?"
Accounting answers:   "Что произошло финансово?"
```

| Слой | Отвечает | Содержит |
|------|----------|----------|
| Knowledge | Происхождение, граф, trust | KnowledgeRevision, Graph, Provenance |
| Accounting | Финансовые факты, проводки | Journal, Entry, Account, Transaction |

**Связь:**

```
KnowledgeRevision
       │ source_document_id
       ▼
Accounting Entry
       │
       ▼
Journal / Ledger
```

Accounting использует document_id из Document Layer.
KnowledgeRevision используется для audit trail (через source_document_id).
Accounting НЕ хранит ссылки на KnowledgeRevision — только на Document.

## 3. Domain Model

### 3.1 Account

```python
@dataclass
class Account:
    account_id: str
    code: str                  # "60" — расчёты с поставщиками
    name: str                  # "Расчеты с поставщиками и подрядчиками"
    type: AccountType          # ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE
    parent_id: str | None      # hierarchical
    is_active: bool = True

class AccountType(Enum):
    ASSET = "asset"            # Актив
    LIABILITY = "liability"    # Пассив
    EQUITY = "equity"          # Капитал
    REVENUE = "revenue"        # Доходы
    EXPENSE = "expense"        # Расходы
```

### 3.2 Period

```python
@dataclass
class AccountingPeriod:
    period_id: str
    name: str                  # "2024-Q1"
    start_date: date
    end_date: date
    status: str                # "OPEN" | "CLOSED" | "LOCKED"
```

### 3.3 Journal

```python
@dataclass
class Journal:
    journal_id: str
    name: str                  # "Журнал операций"
    journal_type: str          # "general" | "sales" | "purchases" | "bank"
    period_id: str
```

### 3.4 Entry (проводка)

```python
@dataclass
class Entry:
    entry_id: str
    journal_id: str
    document_id: str           # from Document Layer (NOT KnowledgeRevision)
    period_id: str
    entry_date: date
    description: str
    lines: list[EntryLine]
    status: str                # "DRAFT" | "VALIDATED" | "POSTED" | "LOCKED"
    created_at: datetime
    posted_at: datetime | None

@dataclass
class EntryLine:
    line_id: str
    account_id: str
    debit: Decimal            # сумма по дебету
    credit: Decimal           # сумма по кредиту
    counterparty_id: str | None
    description: str
```

### 3.5 Transaction (группа проводок)

```python
@dataclass
class AccountingTransaction:
    transaction_id: str
    document_id: str
    entries: list[Entry]
    total_debit: Decimal
    total_credit: Decimal
    status: str                # "DRAFT" | "POSTED" | "REVERSED"
```

### 3.6 Валидация проводок

```python
def validate_entry(entry: Entry) -> list[str]:
    """Проверить корректность проводки."""
    errors = []
    if not entry.lines:
        errors.append("Entry must have at least one line")
    total_debit = sum(l.debit for l in entry.lines)
    total_credit = sum(l.credit for l in entry.lines)
    if total_debit != total_credit:
        errors.append(f"Debit ({total_debit}) != Credit ({total_credit})")
    for line in entry.lines:
        if line.debit > 0 and line.credit > 0:
            errors.append(f"Line {line.line_id}: both debit and credit set")
        if line.debit == 0 and line.credit == 0:
            errors.append(f"Line {line.line_id}: zero amount")
    return errors
```

## 4. Document → Accounting Mapping

### 4.1 Mapping Rules (v1, hardcoded)

```python
# Invoice → Accounting Entry
#   Debit:  Expense account (26)     — amount without VAT
#   Credit: Supplier account (60)    — total with VAT
#   Debit:  Input VAT account (19)   — VAT amount

INVOICE_MAPPING = {
    "debit_expense": {"account_code": "26", "field": "amount"},
    "credit_supplier": {"account_code": "60", "field": "amount"},
    "debit_vat": {"account_code": "19", "field": "vat"},
}

# Act → Accounting Entry
#   Debit:  Expense account (26)
#   Credit: Supplier account (60)

ACT_MAPPING = {
    "debit_expense": {"account_code": "26", "field": "amount"},
    "credit_supplier": {"account_code": "60", "field": "amount"},
}

# Bank Statement → Cash Entry
#   Debit:  Cash account (51)
#   Credit: Counterparty account (76)

BANK_MAPPING = {
    "debit_cash": {"account_code": "51", "field": "amount"},
    "credit_counterparty": {"account_code": "76", "field": "amount"},
}
```

### 4.2 Mapping Service

```python
class AccountingMapper:
    """Transform extracted fields to accounting entries."""

    MAPPINGS = {
        "invoice": INVOICE_MAPPING,
        "act": ACT_MAPPING,
        "bank_statement": BANK_MAPPING,
    }

    def map_to_entry(self, document_id: str, doc_type: str,
                     fields: dict, period_id: str) -> Entry | None:
        mapping = self.MAPPINGS.get(doc_type)
        if not mapping:
            return None

        lines = []
        for line_def in mapping.values():
            account_code = line_def["account_code"]
            field_name = line_def["field"]
            amount = Decimal(str(fields.get(field_name, 0)))
            if amount == 0:
                continue

            # Determine debit/credit from line_def key prefix
            if line_def_name.startswith("debit"):
                debit = amount
                credit = Decimal(0)
            else:
                debit = Decimal(0)
                credit = amount

            lines.append(EntryLine(
                line_id=str(uuid.uuid4()),
                account_id=account_code,
                debit=debit,
                credit=credit,
            ))

        if not lines:
            return None

        return Entry(
            entry_id=str(uuid.uuid4()),
            document_id=document_id,
            period_id=period_id,
            entry_date=...,
            description=f"Auto from {doc_type}",
            lines=lines,
            status="DRAFT",
        )
```

## 5. Accounting Lifecycle

### 5.1 Entry Lifecycle

```
DRAFT
  │  created from document mapping, editable
  ▼
VALIDATED
  │  passed validation (debit = credit), ready to post
  ▼
POSTED
  │  committed to ledger, immutable
  ▼
LOCKED
  │  period closed, no further changes
```

Error states:
- **REJECTED** — validation failed, needs manual correction
- **REVERSED** — reversal entry created

### 5.2 Period Lifecycle

```
OPEN → CLOSING → CLOSED → LOCKED
```

## 6. Storage Model

### 6.1 New tables

```sql
CREATE TABLE accounts (
    account_id  TEXT PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,
    parent_id   TEXT REFERENCES accounts(account_id),
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE accounting_periods (
    period_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    status      TEXT NOT NULL DEFAULT 'OPEN'
);

CREATE TABLE journals (
    journal_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    journal_type TEXT NOT NULL,
    period_id   TEXT NOT NULL REFERENCES accounting_periods(period_id)
);

CREATE TABLE entries (
    entry_id    TEXT PRIMARY KEY,
    journal_id  TEXT NOT NULL REFERENCES journals(journal_id),
    document_id TEXT NOT NULL,
    period_id   TEXT NOT NULL REFERENCES accounting_periods(period_id),
    entry_date  DATE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'DRAFT',
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    posted_at   TIMESTAMP,
    metadata    JSONB DEFAULT '{}'
);

CREATE TABLE entry_lines (
    line_id         TEXT PRIMARY KEY,
    entry_id        TEXT NOT NULL REFERENCES entries(entry_id),
    account_id      TEXT NOT NULL REFERENCES accounts(account_id),
    debit           NUMERIC(18,2) NOT NULL DEFAULT 0,
    credit          NUMERIC(18,2) NOT NULL DEFAULT 0,
    counterparty_id TEXT,
    description     TEXT NOT NULL DEFAULT ''
);
```

### 6.2 Product Layer tables

Все таблицы — Product Layer. Никаких изменений в:
- `knowledge_revisions`
- `projection_store`
- `document_intake`
- `processing_pipelines`
- `routing_decisions`

## 7. Service Boundaries

### 7.1 Product Layer (new)

```
backend/services/accounting/
├── __init__.py
├── models.py              # Domain models
├── repository.py          # PostgreSQL storage
├── mapper.py              # Document → Entry mapping
├── validator.py           # Entry validation (debit = credit)
├── lifecycle.py           # Entry lifecycle transitions
└── ledger.py              # Ledger queries (balance, turnover)
```

### 7.2 Integration points

```
Routing → Accounting:
  • Routing decision == "accounting" triggers Entry creation
  • Uses document_id + profile.fields from Document Layer

Accounting → Routing:
  • NO direct integration
  • Accounting writes entries, routing is done

Accounting → Knowledge:
  • NO direct integration
  • Knowledge tracks origin (via source_document_id)
  • Accounting tracks financial fact

Accounting → Document:
  • Uses document_id for source reference
  • Does NOT own Document lifecycle
```

## 8. API Contracts

### 8.1 Entry CRUD

```
POST   /api/v1/accounting/entries              — Create entry
GET    /api/v1/accounting/entries/{id}          — Get entry with lines
GET    /api/v1/accounting/entries               — List entries (filtered)
PATCH  /api/v1/accounting/entries/{id}          — Update DRAFT entry
```

### 8.2 Entry Lifecycle

```
POST   /api/v1/accounting/entries/{id}/validate — Validate → VALIDATED
POST   /api/v1/accounting/entries/{id}/post     — Post → POSTED
POST   /api/v1/accounting/entries/{id}/reverse  — Create reversal
```

### 8.3 Document → Accounting (from routing)

```
POST   /api/v1/accounting/from-document/{document_id}
       — Auto-create entry from analyzed document
```

### 8.4 Ledger queries

```
GET    /api/v1/accounting/ledger/{account_id}   — Account turnover
GET    /api/v1/accounting/trial-balance          — Trial balance for period
GET    /api/v1/accounting/periods                — List periods
```

## 9. Test Strategy

### 9.1 Unit Tests

```
✓ Entry validation (debit = credit)
✓ Account model creation
✓ Period validation (start < end)
✓ Lifecycle transitions (DRAFT → VALIDATED → POSTED)
✓ Lifecycle errors (POSTED → DRAFT blocked)
✓ Entry line constraints (debit XOR credit)
```

### 9.2 Mapping Tests

```
✓ Invoice → accounting entry (expense + vat + supplier)
✓ Act → accounting entry (expense + supplier)
✓ Bank statement → cash entry
✓ Unknown document type → None
✓ Missing fields → None
✓ Zero amounts → skipped lines
```

### 9.3 Integration Tests

```
✓ Create entry via API
✓ Validate entry
✓ Post entry
✓ Get ledger balance
✓ Trial balance calculation
✓ Document → Accounting auto-create
✓ Full flow: upload → analyze → route → entry created
```

### 9.4 Regression

```
✓ All existing 1157 tests
✓ Platform unchanged (0 files)
✓ Knowledge Layer unchanged
✓ Document Layer unchanged
```

## 10. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Complex accounting rules | Wrong postings | Hardcoded v1 rules, manual validation |
| Period management | Entries in wrong period | Period validation before posting |
| No double-entry knowledge | Users confused | Clear DRAFT → VALIDATE → POST flow |
| Document mapping incomplete | Missing entries | Manual entry creation as fallback |
| Performance at scale | Slow ledger queries | Indexes on period + account |

## 11. Implementation Order

### T1 — Domain Models + Storage

```
Files:
  backend/services/accounting/models.py
  backend/services/accounting/repository.py
  backend/services/accounting/__init__.py

Tables:
  accounts, accounting_periods, journals, entries, entry_lines

Deliverable:
  Full domain model
  PostgreSQL repository with CRUD
  Seed chart of accounts
```

### T2 — Validator + Lifecycle

```
Files:
  backend/services/accounting/validator.py
  backend/services/accounting/lifecycle.py

Deliverable:
  Entry validation (debit = credit)
  Lifecycle transitions (DRAFT → POSTED)
```

### T3 — Document Mapper

```
Files:
  backend/services/accounting/mapper.py

Deliverable:
  Invoice → Entry mapping
  Act → Entry mapping
  Bank Statement → Entry mapping
```

### T4 — Ledger Queries

```
Files:
  backend/services/accounting/ledger.py

Deliverable:
  Account turnover
  Trial balance
```

### T5 — API Endpoints

```
Files:
  backend/api/routes/accounting.py

Deliverable:
  Entry CRUD
  Lifecycle endpoints
  Document → Accounting integration
  Ledger queries
```

### T6 — Integration Tests

```
Files:
  backend/tests/integration/test_accounting.py

Deliverable:
  Full accounting flow tests
  Document → Entry integration
  Regression suite
```

## 12. Architectural Invariants

```
1. Platform frozen           — 0 changes
2. Knowledge immutable       — 0 changes
3. Accounting ≠ Knowledge    — separate layer, separate tables
4. source_document_id links  — Document → Accounting, not Knowledge → Accounting
5. Entry lifecycle           — DRAFT → VALIDATED → POSTED → LOCKED
6. Manual override           — always possible for entries
7. No AI in v1               — hardcoded mapping rules
```

## 13. GO / NO-GO Criteria

**GO** if:
1. ✅ Accounting can be implemented as pure Product Layer
2. ✅ Platform remains frozen (0 changes)
3. ✅ Knowledge Layer unchanged
4. ✅ Entry validation (debit = credit) is deterministic
5. ✅ Document → Entry mapping is explicit (not AI)

**NO-GO** if:
1. ❌ Requires Platform component change
2. ❌ Requires Knowledge Layer modification
3. ❌ Requires AI for v1 mapping
4. ❌ Creates dependency between Accounting and Knowledge internals

```
Phase 0 verdict:

  Product Layer:      ✅ Accounting Domain Model + Document Mapper
  Platform changes:   0 (predicted)
  Knowledge changes:  0
  AI dependency:      None (hardcoded mapping v1)
  GO recommendation:  ✅ STRONG GO
```
