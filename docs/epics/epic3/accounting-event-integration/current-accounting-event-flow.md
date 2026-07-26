# Accounting Event Integration — Phase 0 Discovery

**Date:** 2025-07-26
**Branch:** `feature/accounting-event-integration`
**Author:** Architecture (Phase 0)

---

## 1. Accounting Domain Models

### 1.1 Legacy Accounting (backend/services/accounting/)

**`backend/services/accounting/models.py`** — Stream 1 accounting domain models. Pure dataclasses, NOT ORM:

| Model | File:Line | Notes |
|---|---|---|
| `Account` | `backend/services/accounting/models.py:37` | account_id, code, name, AccountType (ASSET/LIABILITY/EQUITY/REVENUE/EXPENSE), parent_id |
| `AccountingPeriod` | `backend/services/accounting/models.py:47` | period_id, name, start_date, end_date, status (OPEN/CLOSING/CLOSED/LOCKED) |
| `Journal` | `backend/services/accounting/models.py:57` | journal_id, name, journal_type, period_id |
| `EntryLine` | `backend/services/accounting/models.py:64` | line_id, account_id, debit, credit, counterparty_id |
| `AccountingEntry` | `backend/services/accounting/models.py:75` | entry_id, journal_id, document_id, period_id, lines, status (DRAFT→VALIDATED→POSTED→LOCKED) |
| `EntryStatus` | `backend/services/accounting/models.py:19` | DRAFT, VALIDATED, POSTED, LOCKED, REJECTED with transitions |

Tables (expected in PostgreSQL via raw SQL):
- `accounts`, `accounting_periods`, `journals`, `accounting_entries`, `entry_lines`, `ledger_entries`, `journal_entries`, `account_balances`, `journal_sequences`, `reconciliation_runs`, `reconciliation_lines`

**Key observation:** Legacy accounting uses **synchronous psycopg2** connections directly (no async, no SQLAlchemy). `Backend/services/accounting/repository.py` opens/closes connections per operation.

### 1.2 Accounting Binding (services/accounting_binding/)

**Independent service** in `services/accounting_binding/`. Full DDD with contracts, domain, application, infrastructure layers.

**Contracts (Pydantic frozen models):**

| Contract | File:Line | Key Fields |
|---|---|---|
| `AccountingDocument` | `services/accounting_binding/contracts/accounting_document.py:74` | document_id, document_type, entries (list[AccountEntry]), tax_entries, total_debit, total_credit, mapping_hash, status (DRAFT/READY/REVIEW/APPROVED/REJECTED/POSTED) |
| `AccountEntry` | `services/accounting_binding/contracts/accounting_document.py:25` | account_code, side (DEBIT/CREDIT), amount, dimension, description |
| `JournalEntry` | `services/accounting_binding/contracts/journal_entry.py:37` | entry_id, accounting_document_id, lines (list[JournalLine]), total_debit, total_credit, posting_hash |
| `JournalLine` | `services/accounting_binding/contracts/journal_entry.py:19` | account_code, side, amount, dimension, sequence |
| `EnrichedDocument` | `contracts/enriched_document.py` | canonical amounts, dates, counterparty info |
| `NormalizedDocument` | `contracts/normalized_document.py` | raw OCR result |

**Domain layer:**

| Module | Purpose |
|---|---|
| `domain/mapping/mapper.py` | EnrichedDocument → AccountingDocument (account resolution, tax mapping) |
| `domain/posting/poster.py` | AccountingDocument → JournalEntry (double-entry, idempotent via posting_hash) |
| `domain/approval/` | Approval policy + workflow (SUBMIT → REVIEW → APPROVE) |
| `domain/validation/validators.py` | Document validation rules |
| `domain/reporting/service.py` | Reporting (balance sheet, P&L) |
| `domain/deal_resolution/` | Deal resolution (fingerprint, candidate finder, similarity scorer) |
| `domain/business_relationship/` | Knowledge graph, entity resolution, identity matching |

**Infrastructure ORM models:**

| Model | File:Line | Table |
|---|---|---|
| `AccountingDocumentRecord` | `infrastructure/models/accounting_document_record.py:37` | `accounting_documents` |
| `JournalEntryRecord` | `infrastructure/models/journal_entry_record.py:30` | `journal_entries` |
| `OutboxRecord` | `infrastructure/models/outbox_record.py` | `outbox_events` |

Migration `001_initial.py` creates: `accounting_documents`, `journal_entries`, `outbox_events`.

**Key gap:** The Accounting Binding uses **separate tables** (`accounting_documents`, `journal_entries`) from the legacy accounting tables (`accounts`, `accounting_entries`, `ledger_entries`). There are **two parallel accounting systems**.

### 1.3 Accounting Schema in PostgreSQL (via promote_to_deal.py)

The `accounting.document_intake` table is used by the upload/promote pipeline:
- `accounting.document_intake` — documents ingested via OCR, with fields: id, company_id, file_name, classification, confidence, extracted_fields, status, promoted_deal_id, final_type

### Problem / Gaps
- **GAP-1.1:** Two separate accounting models (legacy backend/services/accounting/ vs accounting_binding/) with no documented migration path.
- **GAP-1.2:** No model for **deal-related accounting entries** (commission accrual, deposit tracking, agent commission).
- **GAP-1.3:** `AccountingDocument` has no `deal_id` field — no link to the deal that generated it.
- **GAP-1.4:** Journal entries use `accounting_document_id` as correlation, not `deal_id`.

---

## 2. Current Deal → Accounting Flow

### 2.1 Document → Deal Pipeline (promote_to_deal.py)

`backend/api/routes/promote_to_deal.py` — full lifecycle:

1. Document ingested → `accounting.document_intake`
2. `POST /documents/{id}/promote-to-deal` — creates deal in `public.deals`
3. Sets `price`, `commission=0.0`, `deposit_amount=0.0` from extracted fields
4. Creates `DealEventService` timeline events: `DEAL_CREATED`, `DOCUMENT_ATTACHED`, `ACCOUNTING_INTENT_DETECTED`
5. `AccountingIntentClassifier` (line 120-123): binary classification — `POSTABLE` (payment_order, invoice, receipt) or `NON_POSTABLE` (everything else)
6. Links document to deal via `deal_document_packages`

### 2.2 Deal Context Resolution

`backend/infrastructure/consumers/deal_context_resolution_consumer.py`:
- Consumes `document.ready` event
- Resolves Property (cadastral → address → create)
- Resolves Clients (INN → name → create)
- Updates Deal property_id
- **Emits `deal.updated` event** (line 49, docstring only — actual emit call not shown in the code read)

### 2.3 Deal → Accounting: NO bridge exists

**Key finding:** There is **no service, handler, or pipeline** that listens to `deal.created` or `deal.updated` and generates accounting entries. The connection between Deal and Accounting is **entirely absent**.

What does exist:
- `backend/services/accounting/mapper.py` — maps **documents** (invoice, act, bank_statement) to accounting entries using hardcoded account codes (08, 19, 26, 60, 51, 76). **Not deal-aware.**
- `AccountingIntentClassifier` — marks deal as POSTABLE/NON_POSTABLE but takes **no action** on POSTABLE intent.

### Problem / Gaps
- **GAP-2.1:** No Deal → Accounting bridge at all. `deal.created`, `deal.updated` events are **never consumed for accounting**.
- **GAP-2.2:** Deal financial fields (price, commission, deposit) are set during promote-to-deal but never fed into accounting.
- **GAP-2.3:** `AccountingIntent` is classified but never triggers posting.

---

## 3. Event Contract

### 3.1 Domain Events (backend/core/domain_events.py)

```
EVENT_CLIENT_CREATED   = "client.created"
EVENT_CLIENT_UPDATED   = "client.updated"
EVENT_CLIENT_DELETED   = "client.deleted"
EVENT_PROPERTY_CREATED = "property.created"
EVENT_PROPERTY_UPDATED = "property.updated"
EVENT_PROPERTY_DELETED = "property.deleted"
EVENT_DEAL_CREATED     = "deal.created"        # line 81
EVENT_DEAL_UPDATED     = "deal.updated"         # line 82
EVENT_DEAL_DELETED     = "deal.deleted"         # line 83
EVENT_DOCUMENT_CREATED = "document.created"
EVENT_DOCUMENT_DELETED = "document.deleted"
EVENT_DOCUMENT_READY   = "document.ready"
EVENT_LEAD_CONVERTED   = "lead.converted"
EVENT_LEAD_MERGED      = "lead.merged"
```

**`DomainEvent`** (line 24): `event_type`, `entity_type`, `entity_id` (UUID), `actor_id`, `correlation_id`, `payload` (dict), `occurred_at`.

**`DomainEventBus`** (line 38): Synchronous in-memory bus. `register()` / `emit()` pattern. Handlers called sequentially.

### 3.2 Integration Events (backend/core/integration_event.py)

**`IntegrationEvent`** (line 18): Frozen dataclass for durable delivery. `event_id` (UUID), `event_type`, `aggregate_type`, `aggregate_id`, `occurred_at`, `version`, `payload`.

**`EventAdapter`** (line 67): Converts `DomainEvent` → `IntegrationEvent` for durable outbox delivery.

### 3.3 Event Publisher (backend/infrastructure/event_publisher.py)

Polls `event_outbox` table → delivers to registered consumers. At-least-once with retry + dead letter.

Registered consumers in `backend/main.py`:
- `document.ready` → `DealContextResolutionConsumer`, `GraphSyncConsumer`, `KnowledgeRuntimeConsumer`
- All 14 event types → `GraphSyncConsumer`
- **No consumer for `deal.created`, `deal.updated`, or `deal.deleted` beyond sync handlers**

### 3.4 Sync Event Handlers (backend/core/event_handlers.py)

Registered handlers:
- All events → `audit_handler` (logs to audit log)
- Document events → `embedding_sync_handler`, `search_index_handler`
- **No accounting handler for any deal event**

### Problem / Gaps
- **GAP-3.1:** `deal.created` and `deal.updated` have **no accounting consumers** registered.
- **GAP-3.2:** No `EVENT_ACCOUNTING_*` event types defined.
- **GAP-3.3:** The outbox in `accounting_binding` (`OutboxEventType`: DOCUMENT_READY, DOCUMENT_APPROVED, POSTING_REQUESTED, etc.) is separate from the main event outbox. Two outbox systems.

---

## 4. Financial Fields

### 4.1 Deal Model (`backend/models/deal.py`)

```python
class Deal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deals"

    price: Mapped[float]           # line 20 — Numeric(15, 2), NOT NULL
    price_currency: Mapped[str]    # line 21 — String(3), default "RUB"
    commission: Mapped[float | None]    # line 22 — Numeric(15, 2), default 0
    commission_percent: Mapped[float | None]  # line 23 — Numeric(5, 2)
    deposit_amount: Mapped[float | None]     # line 24 — Numeric(15, 2)
```

Other fields: `deal_type`, `status`, `property_id`, `title`, `start_date`, `end_date`, `closing_date`, `source`.

### 4.2 How Financial Fields Are Set

In `promote_to_deal.py` (line 216-222):
```python
INSERT INTO public.deals (id, deal_type, status, lifecycle_stage, property_id, title, description,
    price, price_currency, commission, deposit_amount, start_date, source, created_by, created_at, updated_at)
VALUES ($1, $2, 'initiated', $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $14)
```
- `price` — extracted from document amounts (max amount)
- `commission` — **always 0.0** (line 220)
- `deposit_amount` — **always 0.0** (line 220)
- `price_currency` — hardcoded "RUB"

### Problem / Gaps
- **GAP-4.1:** `commission` and `deposit_amount` are always set to `0.0` during promote-to-deal — never extracted from documents.
- **GAP-4.2:** No commission calculation logic exists (commission_percent is set on model but never populated).
- **GAP-4.3:** Financial fields are **not used anywhere** after deal creation — no accounting entries are generated from price/commission/deposit.
- **GAP-4.4:** No payment schedule, installment tracking, or payment status on the Deal model.

---

## 5. Existing Services

### 5.1 Legacy Accounting Services (`backend/services/accounting/`)

| Service | File | Purpose | Status |
|---|---|---|---|
| `AccountingRepository` | `repository.py` | PostgreSQL CRUD for accounts, periods, entries | Synchronous, psycopg2 |
| `PostingService` | `posting.py` | Journal sequence, ledger posting, period management | Synchronous, psycopg2 |
| `AccountingMapper` | `mapper.py` | Document → entry mapping (hardcoded rules for invoice/act/bank_statement) | Synchronous |
| `PeriodCloser` | `closing.py` | Multi-step period closing (verify trial balance → close nominal → lock) | Synchronous |
| `ReconciliationService` | `reconciliation.py` | Bank ↔ cash ledger matching | Synchronous |
| `ReportingService` | `reporting.py` | Balance sheet, P&L queries | Synchronous |

**All services use synchronous psycopg2** — NOT compatible with the async FastAPI stack.

### 5.2 Accounting Binding Services (`services/accounting_binding/`)

| Layer | Module | Purpose |
|---|---|---|
| **Application** | `application/workflows/accounting_pipeline.py` | Orchestrator: enrich → validate → map → approve → post |
| **Application** | `application/capabilities/` | Audit, consistency check, governance, recovery, search, traversal, trust state |
| **Application** | `application/knowledge_persistence/` | Knowledge graph persistence, runtime integration |
| **Domain** | `domain/mapping/mapper.py` | EnrichedDocument → AccountingDocument mapping |
| **Domain** | `domain/posting/poster.py` | AccountingDocument → JournalEntry posting (idempotent, append-only) |
| **Domain** | `domain/approval/` | Approval policy + workflow (SUBMIT → REVIEW → APPROVE) |
| **Domain** | `domain/deal_resolution/` | Document fingerprint → deal matching |
| **Domain** | `domain/business_relationship/` | Knowledge graph, entity resolution, provenance |
| **Infrastructure** | `infrastructure/events/outbox.py` | Transactional outbox pattern for posting events |
| **Infrastructure** | `infrastructure/repositories/` | Journal repo, accounting document repo |
| **Infrastructure** | `infrastructure/models/` | ORM records (accounting_documents, journal_entries, outbox_events) |
| **Infrastructure** | `infrastructure/migrations/` | Alembic forward-only migration |
| **API** | `api/routes/replay.py` | Replay endpoint |

### 5.3 Deal-Related Services (`backend/services/`)

| Service | File | Purpose |
|---|---|---|
| `DealService` | `services/deal_service.py` | Deal lifecycle (create, status transitions, property attach, emit events) |
| `DealContextResolver` | `services/deal_context_resolution/` | Resolve property/clients from document profile |
| `DealApplicationService` | `services/deal_context_resolution/application_service.py` | Log resolution attempts |

### 5.4 Consumers

| Consumer | Event Source | Purpose |
|---|---|---|
| `DealContextResolutionConsumer` | `document.ready` | Resolve property + clients → update deal → emit `deal.updated` |
| `GraphSyncConsumer` | All events | Sync to graph DB |
| `KnowledgeRuntimeConsumer` | `document.ready` | Knowledge runtime integration |

### Problem / Gaps
- **GAP-5.1:** Legacy accounting (`backend/services/accounting/`) uses synchronous psycopg2 — cannot be used in async FastAPI handlers without wrapper.
- **GAP-5.2:** Accounting Binding (`services/accounting_binding/`) uses separate DB tables from legacy accounting — two parallel systems.
- **GAP-5.3:** No accounting service is registered as a consumer of deal events.
- **GAP-5.4:** Accounting Binding's pipeline (`accounting_pipeline.py`) processes documents (via NormalizedDocument → EnrichedDocument → AccountingDocument), not deals.
- **GAP-5.5:** The `deal_resolution` module in accounting_binding deals with document→deal matching, not deal→accounting.

---

## 6. Key Findings

### 6.1 Summary of Current State

```
[OCR Document]
    ↓ document.ready
[DealContextResolutionConsumer] → resolves property/clients → updates Deal
    ↓ deal.updated (event emitted, NO accounting consumer)
[DealService] — lifecycle management
    ↓ price, commission=0, deposit=0 stored on Deal
[AccountingIntentClassifier] — POSTABLE/NON_POSTABLE — CLASSIFIED BUT NOT ACTED UPON
    ↓
❌ NO BRIDGE TO ACCOUNTING
```

### 6.2 Critical Gaps

| # | Gap | Severity |
|---|---|---|
| GAP-1 | No Deal → Accounting bridge (no handler for deal events) | **BLOCKER** |
| GAP-2 | Two parallel accounting systems (legacy + accounting_binding) | **HIGH** |
| GAP-3 | Deal financial fields (commission, deposit) always 0 | **HIGH** |
| GAP-4 | No accounting event types defined (EVENT_ACCOUNTING_*) | **MEDIUM** |
| GAP-5 | Legacy accounting services are synchronous (psycopg2) | **MEDIUM** |
| GAP-6 | AccountingIntent is classified but never triggers posting | **MEDIUM** |
| GAP-7 | No deal_id in AccountingDocument/JournalEntry models | **MEDIUM** |
| GAP-8 | Two separate outbox systems (main + accounting_binding) | **LOW** |

### 6.3 Existing Infrastructure That CAN Be Reused

1. **DomainEventBus** + `deal.created`/`deal.updated` events — ready to register new consumers
2. **Accounting Binding pipeline** (`AccountingPipeline.run()` + `execute_posting()`) — ready for document-based accounting
3. **Accounting Binding posting** (`PostingService.post()`) — idempotent, append-only journal entries
4. **Accounting Binding contracts** (`AccountingDocument`, `JournalEntry`, `AccountEntry`) — well-defined domain contracts
5. **Deal financial fields** (`price`, `commission`, `deposit_amount`) — populated on Deal model
6. **Transactional outbox** pattern — already implemented in both systems

---

## 7. Recommendation for Phase 1

### Primary Recommendation: Build Deal → Accounting Bridge

**Goal:** Register a consumer on `deal.updated` that creates accounting entries for deal financials.

**Suggested Architecture:**

```
[deal.updated event]
    ↓
[DealAccountingConsumer] (new, registered in main.py)
    ↓
1. Load Deal from DB (price, commission, deposit_amount, property_id)
2. Build AccountingDocument from deal financials
3. Run AccountingBinding pipeline (or subset)
4. Create JournalEntry for:
   - Commission accrual (Дт 62 / Кт 90) — agent commission receivable
   - Deposit tracking (Дт 51 / Кт 76) — deposit received
   - Deal value (Дт 08 / Кт 60) — transaction value
5. Emit accounting.posted event
```

### Phase 1 Scope (Suggested)

1. **Define** `deal.accounting_intent_detected` event type or reuse `deal.updated`
2. **Create** `DealAccountingConsumer` class
3. **Register** consumer on `deal.updated` in `backend/main.py`
4. **Implement** deal → accounting document mapping (commission, deposit, price → entries)
5. **Add** `deal_id` correlation to `AccountingDocument`
6. **Test** with existing deal fixtures

### Out of Scope for Phase 1

- Full commission calculation engine (commission_percent not yet populated)
- Payment schedule / installment tracking
- Period closing integration
- Migration from legacy accounting tables
- Accounting Binding's full pipeline (use only posting sub-domain)
