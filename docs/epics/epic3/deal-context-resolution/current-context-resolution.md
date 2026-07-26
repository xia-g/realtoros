# Phase 0 Discovery: Deal Context Resolution

> **Branch:** `feature/deal-context-resolution`
> **Date:** 2026-07-26
> **Author:** Architect RealtorOS
> **Status:** ✅ Complete
> **Base:** `master` (epic3-stream3-business-events-complete merged)

---

## 1. Deal Model

### 1.1 SQLAlchemy Model

**File:** `backend/models/deal.py` (lines 12–40)

```python
class Deal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deals"

    deal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="negotiation", nullable=False)
    property_id = mapped_column(ForeignKey("properties.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    price_currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    commission: Mapped[float | None] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    commission_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    deposit_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
```

### 1.2 Key Observations

| Field | Type | Nullable? | Default | Notes |
|-------|------|-----------|---------|-------|
| `deal_type` | String(20) | ❌ No | — | `purchase`, `payment`, `expense`, `registration`, `other` |
| `status` | String(20) | ❌ No | `negotiation` | Also `initiated` (from promote_to_deal) |
| `property_id` | FK → properties.id | ❌ No | — | **Model says NOT NULL, but promote_to_deal passes None** |
| `price` | Numeric(15,2) | ❌ No | — | Always set |
| `price_currency` | String(3) | ❌ No | `RUB` | |
| `start_date` | Date | ❌ No | — | `date.today()` in promote_to_deal |
| `source` | String(50) | ❌ No | `other` | `ocr_ingestion` from promote_to_deal |
| `created_by` | FK → users.id | ❌ No | — | Hardcoded system user in promote_to_deal |
| `commission` | Numeric(15,2) | ✅ Yes | `0` | |
| `description` | Text | ✅ Yes | — | |
| `notes` | Text | ✅ Yes | — | |
| `end_date` | Date | ✅ Yes | — | |
| `closing_date` | Date | ✅ Yes | — | |

### 1.3 Relationships

```python
property: Mapped["Property"] = relationship("Property", back_populates="deals")
participants: Mapped[list["DealParticipant"]] = relationship("DealParticipant", back_populates="deal", cascade="all, delete-orphan")
creator: Mapped["User"] = relationship("User", back_populates="deals_created", foreign_keys=[created_by])
documents: Mapped[list["Document"]] = relationship("Document", back_populates="deal")
communications: Mapped[list["Communication"]] = relationship("Communication", back_populates="deal")
tasks: Mapped[list["Task"]] = relationship("Task", back_populates="deal")
checkpoints: Mapped[list["DealCheckpoint"]] = relationship("DealCheckpoint", back_populates="deal", cascade="all, delete-orphan")
workflows: Mapped[list["DealWorkflow"]] = relationship("DealWorkflow", back_populates="deal", cascade="all, delete-orphan")
```

**CRITICAL: No direct `client_id` on Deal.** Clients are linked via `DealParticipant` only.

### 1.4 DealParticipant Model

**File:** `backend/models/deal_participant.py` (lines 12–22)

```python
class DealParticipant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_participants"

    deal_id = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    client_id = mapped_column(ForeignKey("clients.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
```

- `client_id` → links to `Client` model (full_name, phone, email, telegram, INN — but **no INN field on Client** currently)
- `role` — `buyer`, `seller`, `counterparty`, etc.
- No `party_name`, no `inn`, no `confidence` score, no `party_source` field

### 1.5 Client Model

**File:** `backend/models/client.py` (lines 13–34)

```python
class Client(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    type: Mapped[str] = mapped_column(String(20), default="buyer")     # buyer, seller, etc.
    status: Mapped[str] = mapped_column(String(20), default="lead")    # lead, active, archived
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="other")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list, nullable=True)
    created_by = mapped_column(ForeignKey("users.id"), nullable=True)
```

**No INN field on Client.** Passport fields, legal entity details — all absent.

### 1.6 Property Model

**File:** `backend/models/property.py` (lines 13–41)

```python
class Property(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "properties"

    property_type: Mapped[str] = mapped_column(String(20), nullable=False)  # apartment, house, commercial, land
    status: Mapped[str] = mapped_column(String(20), default="available")
    deal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    area_total: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    area_living: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floors_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    price_currency: Mapped[str] = mapped_column(String(3), default="RUB")
    price_per_meter: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    commission: Mapped[float | None] = mapped_column(Numeric(15, 2), default=0, nullable=True)
    owner_id = mapped_column(ForeignKey("clients.id"), nullable=True)
    ...
```

- `owner_id` → FK to Client (optional)
- **No cadastral_number on Property model** (but extracted by OCR and used in resolution)
- **No normalized_address** field (raw `address` field only)

---

## 2. Null Zones

### 2.1 promote_to_deal — Current Gaps

**File:** `backend/api/routes/promote_to_deal.py` (lines 196–222)

The **only** Deal creation path from documents:

```python
# Line 219 — property_id is explicitly passed as None!
await conn.execute(
    """INSERT INTO public.deals (id, deal_type, status, lifecycle_stage, property_id, ...)
       VALUES ($1, $2, 'initiated', $3, $4, ...)""",
    deal_id, deal_type, LifecycleStage.DEAL_CANDIDATE.value,
    None,  # <-- property_id = NULL!
    ...
)
```

**Null zones after promote_to_deal:**

| Field | Value | Problem? |
|-------|-------|----------|
| `property_id` | `NULL` | ✅ Model says NOT NULL, DB allows NULL — property unknown |
| `participants` | `[]` | ❌ Parties extracted but **never persisted** as DealParticipant |
| `commission` | `0.0` | Hardcoded — should be derived from price |
| `deposit_amount` | `0.0` | Hardcoded |
| `created_by` | Hardcoded UUID `5055acf6-...` | System user, no real agent identity |
| `lifecycle_stage` | `deal_candidate` | Added field (not in Deal SQLAlchemy model) |

### 2.2 Existing Resolvers / Filler Functions

**None.** There is no existing code that:
- Fills `property_id` on a Deal post-creation
- Creates `DealParticipant` records from extracted document parties
- Links a Deal to a Client or Property automatically

The only resolution-like code is in `backend/api/routes/deal_resolution.py` (POST `/documents/{id}/resolve`) but it is **read-only** — it returns a `ResolutionResult` but never modifies DB.

**File:** `backend/api/routes/deal_resolution.py` (line 6)

> Read-only: возвращает ResolutionResult, не создаёт сделки.

### 2.3 Summary of Null/Empty Zones

```
Deal after promote_to_deal:
├── property_id          → NULL        ← needs Property resolution
├── participants         → []          ← needs Client resolution + DealParticipant creation
├── commission           → 0.0         ← needs calculation from profile
├── deposit_amount       → 0.0         ← needs extraction from profile
├── created_by           → system UUID ← needs real agent
└── lifecycle_stage      → deal_candidate
```

---

## 3. DocumentReady Contract

### 3.1 DomainEvent Definition

**File:** `backend/core/domain_events.py` (line 87)

```python
EVENT_DOCUMENT_READY = "document.ready"
```

DomainEvent is a simple dataclass:

**File:** `backend/core/domain_events.py` (lines 23–32)

```python
@dataclass
class DomainEvent:
    event_type: str
    entity_type: str
    entity_id: UUID
    actor_id: str = "system"
    correlation_id: str = ""
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### 3.2 mark_document_ready — Payload Construction

**File:** `backend/services/document_lifecycle.py` (lines 111–188)

```python
payload = {
    "status": doc.status,              # "READY"
    "previous_status": previous_status, # "ANALYZED" or "NEEDS_REVIEW"
    "document_id": doc.document_id,
    "organization_id": doc.organization_id,
    "contract_number": profile.get("contract_number", ""),
    "total_price": profile.get("total_price", ""),
    "buyer_name": profile.get("buyer_name", ""),
    "seller_name": profile.get("seller_name", ""),
    "profile": profile,                 # full JSONB profile from pipeline
}
```

### 3.3 Profile Content (source of truth for resolution)

The profile is populated by the processing pipeline in `backend/api/routes/processing.py` (lines 79–101):

```python
doc.profile["document_type"] = classification result
doc.profile["classification_confidence"] = ...
doc.profile["fields"] = s.result.get("fields", {})
doc.profile["extraction_confidence"] = ...
doc.profile["profile"] = extraction_profile          # structured v2 profile
doc.profile["profile_version"] = extraction_profile.get("profile_version", "1.0")
doc.profile["contract_number"] = sections["identification"].get("contract_number")
doc.profile["seller_name"] = sections["parties"]["seller"].get("name")
doc.profile["buyer_name"] = sections["parties"]["buyer"].get("name")
doc.profile["total_price"] = sections["financial_terms"]["total_price"].get("value")
```

### 3.4 ContractProfile Structure (v2)

**File:** `backend/services/processing/extraction/__init__.py` (lines 171–254)

```python
{
    "profile_version": "1.0",
    "confidence": 0.85,
    "sections": {
        "identification": {
            "contract_number": "2182-НШИИ",
            "contract_date": "2025-03-15",
            "place_of_signing": "Санкт-Петербург"
        },
        "parties": {
            "seller": {
                "name": "ООО Ромашка",
                "type": "legal",
                "inn": "7801234567",
                "kpp": "780101001",
                "ogrn": "1027801234567"
            },
            "buyer": {
                "name": "Иван Иванов",
                "type": "individual",
                "inn": "123456789012",
                "kpp": None,
                "ogrn": None
            }
        },
        "financial_terms": {
            "total_price": {"value": 5000000.0, "currency": "RUB"},
            "vat_amount": None,
            "deposit_amount": {"value": 500000.0, "currency": "RUB"}
        },
        "property": {
            "address": "г. Санкт-Петербург, ул. Ленина, д. 1, кв. 1",
            "area_sqm": 45.5,
            "floor": 3,
            "cadastral_number": "78:01:0001001:1234",
            "property_type": "residential"
        },
        "dates": {
            "signing_date": "2025-03-15",
            "payment_deadline": "2025-04-15",
            "transfer_deadline": "2025-05-01"
        }
    }
}
```

### 3.5 Is DocumentReady Enough for Resolution?

| What we need | Available in DocumentReady payload? | Source |
|---|---|---|
| `document_id` | ✅ Yes | `payload.document_id` |
| `buyer_name` | ✅ Yes (top-level) | `payload.buyer_name` |
| `seller_name` | ✅ Yes (top-level) | `payload.seller_name` |
| `contract_number` | ✅ Yes | `payload.contract_number` |
| `total_price` | ✅ Yes | `payload.total_price` |
| Full profile | ✅ Yes | `payload.profile` (full JSONB) |
| Cadastral number | ✅ Yes | `profile.sections.property.cadastral_number` |
| Property address | ✅ Yes | `profile.sections.property.address` |
| Buyer INN | ✅ Yes | `profile.sections.parties.buyer.inn` |
| Seller INN | ✅ Yes | `profile.sections.parties.seller.inn` |
| Buyer KPP/OGRN | ✅ Yes | `profile.sections.parties.buyer.*` |
| Deposit amount | ✅ Yes | `profile.sections.financial_terms.deposit_amount` |
| OCR raw text | ❌ No (not in event) | Available via OCR Node API |
| Extracted entities | ❌ No (only in extracted_fields) | Available via `document_intake.extracted_fields` |

**Conclusion: DocumentReady payload contains sufficient data for Deal Context Resolution.** The structured ContractProfile has all essential fields: parties (buyer/seller with INN), property (cadastral, address), financial terms.

### 3.6 IntegrationEvent Envelope

**File:** `backend/core/integration_event.py` (lines 17–34)

```python
@dataclass(frozen=True)
class IntegrationEvent:
    event_id: UUID
    event_type: str
    aggregate_type: str          # "Document"
    aggregate_id: str            # doc.document_id
    occurred_at: datetime
    version: int = 1
    payload: dict                # same as domain event payload
    metadata: dict | None = None # schema_version, producer, correlation_id
```

**EventAdapter** (lines 67–116) converts DomainEvent → IntegrationEvent.

---

## 4. Existing Knowledge

### 4.1 Graph Nodes

**File:** `backend/models/graph_node.py` (lines 16–27)

```python
class GraphNode(UUIDMixin, Base):
    __tablename__ = "graph_nodes"

    node_type: str               # Document, Deal, Client, Property
    entity_id: UUID              # stable business entity ID
    source_entity_type: str      # client | property | deal | document | regulation
    source_entity_id: UUID       # FK to source
    title: str
    meta: dict | None            # JSONB — arbitrary metadata
    deleted_at: datetime | None
```

Nodes store `source_entity_type` + `source_entity_id` for referential integrity.

### 4.2 GraphSyncConsumer

**File:** `backend/infrastructure/consumers/graph_sync_consumer.py`

Consumes IntegrationEvents and syncs entities to the graph via `GraphLifecycleService.sync_entity()`.

- Registered for `document.ready` events
- Calls `GraphLifecycleService.sync_entity(entity_type="Document", entity_id=..., title="document")`
- `GraphLifecycleService` (file: `backend/services/graph_lifecycle_service.py`) creates/updates GraphNode with `source_entity_type` + `source_entity_id`

### 4.3 Extraction Results Location

| Data | Where | Schema |
|------|-------|--------|
| OCR raw text | OCR Node (port 8001) | `normalized_document.raw_text` |
| Extracted fields (flat) | `document_intake.extracted_fields` (JSONB) | `{amounts:[], dates:[], inn, counterparty}` |
| Structured profile | `document_intake.profile` (JSONB) → `profile.sections` | ContractProfile structure |
| Classification | `document_intake.classification` | `contract`, `invoice`, etc. |
| Parties (semantic) | Stored in response, not persisted for search | `party_result.parties` |

### 4.4 What Knowledge Is Available for Reuse

1. **GraphNode** — entity nodes exist for documents, deals (from previous sync)
2. **GraphEdge** — relationships between entities exist (file: `backend/models/graph_edge.py`)
3. **ContractProfile** — structured extraction with buyer/seller INN, cadastral, address
4. **DocumentFingerprint** (accounting_binding) — reusable fingerprint abstraction
5. **DealResolver** — read-only resolution engine (good for Phase 1 but needs write support)
6. **CandidateFinder** — search by cadastral, address, parties, contract number, date

### 4.5 Existing Knowledge Gaps

| Gap | Impact |
|-----|--------|
| **No Client INN storage** | Client model lacks INN — impossible to match OCR party INN to existing Client |
| **No Property cadastral** | Property model lacks cadastral_number — impossible to match OCR cadastral to Property |
| **No party link from Deal** | Deal has no buyer/seller name/INN on Deal itself — CandidateFinder searches `deals.title` only |
| **Graph sync is minimal** | GraphSyncConsumer only stores entity_id + title — no profile metadata in graph |

---

## 5. Deal Creation Flow

### 5.1 Two Deal Creation Paths

#### Path A: promote_to_deal (asyncpg, document-intake based)

**File:** `backend/api/routes/promote_to_deal.py`

```
POST /documents/{id}/promote-to-deal
```

Flow:
1. `Idempotency check` — if `promoted_deal_id` already set, return existing
2. `Confidence gate` — ≥0.90 auto, ≥0.70 review, <0.70 reject
3. `Parse extracted_fields` → `fields` + `parties`
4. `Create Deal` — INSERT with `property_id=NULL`, no participants
5. `Mark document_intake` with `promoted_deal_id`
6. `Create Document record` linked to deal
7. `Create deal_document_packages` for requirements
8. `Emit timeline events`: DEAL_CREATED, DOCUMENT_ATTACHED, ACCOUNTING_INTENT

**No DomainEventBus events emitted** — only timeline events (local table).

#### Path B: DealService.create_deal (SQLAlchemy, manual)

**File:** `backend/services/deal_service.py` (lines 31–68)

```python
async def create_deal(self, *, property_id=None, deal_type="buy", status="negotiation",
                      created_by=None, participants=None, **extra):
    if not participants:
        raise ValidationError("At least one participant is required")
    deal = await self.repo.create(...)
    for client_id in participants:
        participant = DealParticipant(deal_id=deal.id, client_id=client_id, role="buyer"/"seller")
        self.session.add(participant)
    await self.session.flush()
    return deal
```

**File:** `backend/services/deal.py` (lines 41–44) — also emits `EVENT_DEAL_CREATED` via DomainEventBus:

```python
async def create(self, **kwargs):
    obj = await super().create(**kwargs)
    await self._emit(EVENT_DEAL_CREATED, obj.id, **kwargs)
    return obj
```

Path B is **not used** by document ingestion (promote_to_deal uses raw asyncpg).

### 5.2 Events Emitted During Deal Creation

| Event Type | Source | Mechanism | Consumer |
|---|---|---|---|
| `deal.created` | `DealService._emit` | DomainEventBus | In-memory handlers |
| `DEAL_CREATED` timeline | `DealEventService.emit` | Direct SQL insert | None |
| `document.ready` | `mark_document_ready` | DomainEventBus → EventAdapter → Outbox → Publisher → GraphSyncConsumer | Graph sync |

**No `document.ready` consumer for Deal Context Resolution exists yet.**

### 5.3 API Endpoints for Deals

| Endpoint | Method | Source |
|---|---|---|
| `GET /deals` | asyncpg | `backend/api/deals.py` |
| `GET /deals/{id}` | asyncpg | `backend/api/deals.py` |
| `POST /documents/{id}/promote-to-deal` | asyncpg | `backend/api/routes/promote_to_deal.py` |
| `POST /documents/{id}/bind-to-deal/{deal_id}` | asyncpg | `backend/api/routes/promote_to_deal.py` |
| `POST /documents/{id}/resolve` | asyncpg | `backend/api/routes/deal_resolution.py` |
| `GET /deals/{id}/requirements` | asyncpg | `backend/api/routes/promote_to_deal.py` |
| `GET /deals/{id}/timeline` | asyncpg | `backend/api/routes/promote_to_deal.py` |

### 5.4 Deal PATCH/Update Endpoint

**No PATCH endpoint for deals** — the Deals API only has GET and POST. There is no API to update `property_id` or add participants after creation.

---

## 6. Key Findings

### 6.1 Critical Gaps

1. **No post-creation Deal enrichment.** `promote_to_deal` creates a Deal skeleton (property_id=NULL, no participants). There is no consumer that listens to `document.ready` and fills in the gaps.

2. **No Client-from-document creation.** OCR extracts buyer/seller names with INN, but there's no code that creates/links `Client` records from document parties.

3. **No Property-from-document creation.** OCR extracts cadastral number and address, but there's no code that creates/links `Property` records.

4. **Client model lacks INN.** Matching OCR parties to existing clients requires INN on the Client model.

5. **Property model lacks cadastral_number.** Matching OCR cadastral to existing property requires cadastral_number on the Property model.

6. **No Deal update API.** PATCH/update for property_id, participants does not exist.

### 6.2 Existing Strengths

1. **Rich DocumentReady payload** — contains buyer_name, seller_name, full ContractProfile with cadastral, address, INN, price. Enough for resolution.

2. **Event Backbone works** — `document.ready` → Outbox → Publisher → Consumer with dedup is proven (Stream 3 complete).

3. **DealResolver exists** — read-only resolution engine with fingerprint, candidate finding, similarity scoring. Can be extended for Phase 1.

4. **CandidateFinder works** — searches by cadastral, address, parties, contract number, date.

5. **ContractProfile is structured** — parties section with seller/buyer + INN is directly usable.

### 6.3 What the DocumentReady Consumer Currently Handles

Currently, `GraphSyncConsumer` handles `document.ready` events by syncing the document to the knowledge graph. **No consumer fills Deal context.** This is the gap Phase 1 must address.

### 6.4 Deal Lifecycle Stage

The `deals` table has a `lifecycle_stage` column (not in SQLAlchemy model but in DB):

```
deal_candidate → document_review → ready_for_accounting → completed
```

Set to `deal_candidate` in promote_to_deal. This could be used as a signal: "deal needs context resolution."

---

## 7. Recommendation for Phase 1

### 7.1 Build: DealContextResolutionConsumer

Register a new consumer for `document.ready` events that:

1. **Fetches full profile** from DocumentReady payload (`contract_number`, `total_price`, `buyer_name`, `seller_name`, profile sections)
2. **Resolves Property** — search by cadastral_number or address → create or link `Property`
3. **Resolves Clients** — search by INN or name → create or link `Client` records
4. **Creates DealParticipant** — link resolved clients with roles (buyer/seller)
5. **Updates Deal** — set `property_id`, update `commission`, `deposit_amount` from profile
6. **Emit events** — `deal.updated`, `participant.added` for downstream consumers

### 7.2 Architectural Decisions for Phase 1

| Decision | Options | Recommendation |
|---|---|---|
| **Consumer type** | New consumer vs. extend GraphSyncConsumer | **New consumer** — separation of concerns |
| **How to find target Deal** | `aggregate_id` (document) → find deal via `promoted_deal_id` | Use `document_intake.promoted_deal_id` |
| **Client matching strategy** | INN first, then name+phone, then mark for review | Try INN → name fuzzy → create if not found |
| **Property matching strategy** | Cadastral → address → create if not found | Use existing CandidateFinder logic |
| **Deal update mechanism** | Direct SQL vs. DealService | Direct SQL (consistency with promote_to_deal pattern) |
| **Error handling** | Idempotent, retryable, DLQ | If resolution fails → mark deal lifecycle_stage = `needs_review` |

### 7.3 Required Schema Changes

1. **Client model**: Add `inn` field (String(12), nullable, unique)
2. **Property model**: Add `cadastral_number` field (String(50), nullable, unique index)
3. **Deal model**: Add `lifecycle_stage` column to SQLAlchemy model (already in DB)
4. **Deal model**: Consider adding denormalized `buyer_name`/`seller_name` for fast search

### 7.4 What NOT to Do (Scope Guard)

- ❌ New Event Backbone — Stream 3 is complete
- ❌ New Knowledge Graph — GraphNode/GraphEdge exist
- ❌ New CRM — Client model exists
- ❌ New Matching Engine — DealResolver + CandidateFinder exist (read-only)
- ❌ Rewriting Deal domain — Deal model is fine
- ❌ Changing Document lifecycle — UPLOADED→READY works
- ❌ Changing existing events — `document.ready` payload is sufficient

### 7.5 Suggested Implementation Order

| Step | Description | Dependencies |
|------|-------------|-------------|
| 1 | Add `inn` to Client, `cadastral_number` to Property | Schema migration |
| 2 | Register `DealContextResolutionConsumer` for `document.ready` | Step 1 |
| 3 | Implement Property resolution (cadastral→address→create) | Step 2 |
| 4 | Implement Client resolution (INN→name→create) | Step 2 |
| 5 | Implement Deal update (property_id, participants, commission) | Steps 3+4 |
| 6 | Add PATCH /deals/{id} endpoint for manual override | Step 5 |
| 7 | Migration: backfill existing deals (null property_id → resolve) | Steps 1–5 |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-26 | New consumer (not extend GraphSyncConsumer) | Separation of concerns; GraphSync is for graph sync, DealContextResolution is for deal enrichment |
| 2026-07-26 | Use `document_intake.promoted_deal_id` as link to deal | Existing FK; no need for separate mapping |
| 2026-07-26 | Read-only DealResolver is sufficient for Phase 1 matching | Already has fingerprint, candidate finding, similarity scoring |
| 2026-07-26 | Add `inn` to Client, `cadastral_number` to Property | Required for matching; currently impossible |

---

## Resource Addresses

| Resource | Path | Lines |
|----------|------|-------|
| Deal model | `backend/models/deal.py` | 12–40 |
| DealParticipant model | `backend/models/deal_participant.py` | 12–22 |
| Client model | `backend/models/client.py` | 13–34 |
| Property model | `backend/models/property.py` | 13–41 |
| Document model | `backend/models/document.py` | 12–35 |
| DomainEvent | `backend/core/domain_events.py` | 23–32, 87 |
| IntegrationEvent | `backend/core/integration_event.py` | 17–64 |
| EventAdapter | `backend/core/integration_event.py` | 67–116 |
| EventOutbox model | `backend/models/event_outbox.py` | 21–58 |
| BusinessEvent model | `backend/models/business_events.py` | 21–44 |
| EventPublisher | `backend/infrastructure/event_publisher.py` | 30–303 |
| BaseConsumer | `backend/infrastructure/consumer_base.py` | 50–109 |
| GraphSyncConsumer | `backend/infrastructure/consumers/graph_sync_consumer.py` | 25–68 |
| GraphLifecycleService | `backend/services/graph_lifecycle_service.py` | 19–109 |
| GraphNode model | `backend/models/graph_node.py` | 16–27 |
| `mark_document_ready` | `backend/services/document_lifecycle.py` | 111–188 |
| DocumentRepository | `backend/services/document_lifecycle.py` | 215–364 |
| promote_to_deal | `backend/api/routes/promote_to_deal.py` | 144–298 |
| bind_to_deal | `backend/api/routes/promote_to_deal.py` | 350–459 |
| DealService (service) | `backend/services/deal.py` | 16–73 |
| DealService (manual) | `backend/services/deal_service.py` | 26–129 |
| Deals API (asyncpg) | `backend/api/deals.py` | 1–92 |
| Deal Resolution API | `backend/api/routes/deal_resolution.py` | 1–191 |
| Processing pipeline | `backend/api/routes/processing.py` | 34–126 |
| Processing → profile | `backend/api/routes/processing.py` | 79–101 |
| DocumentFingerprint | `services/accounting_binding/domain/deal_resolution/fingerprint.py` | 69–102 |
| TransactionFingerprint | `services/accounting_binding/domain/deal_resolution/fingerprint.py` | 106–186 |
| DealResolver | `services/accounting_binding/domain/deal_resolution/resolver.py` | 77–157 |
| CandidateFinder | `services/accounting_binding/domain/deal_resolution/candidate_finder.py` | 81–144 |
| SimilarityScorer | `services/accounting_binding/domain/deal_resolution/similarity_scorer.py` | 22–195 |
| ContractProfile | `backend/services/processing/extraction/__init__.py` | 171–254 |
| Parties section | `backend/services/processing/extraction/__init__.py` | 91–98, 205–219 |
| Property section | `backend/services/processing/extraction/__init__.py` | 116–126, 228–234 |
| Extraction step v1 | `backend/services/processing/steps/extraction_step.py` | 59–81 |
| Extraction step v2 | `backend/services/processing/steps/extraction_step.py` | 84–120 |
| Upload/OCR processing | `backend/api/routes/uploads.py` | 590–655 |
| Upload deal resolution | `backend/api/routes/uploads.py` | 311–378 |
| DOC_TO_ROLE mapping | `backend/api/routes/promote_to_deal.py` | 75–84 |
| DOC_TO_DEAL_TYPE | `backend/api/routes/promote_to_deal.py` | 100–105 |
| Lifecycle VALID_TRANSITIONS | `backend/services/document_lifecycle.py` | 29–41 |
