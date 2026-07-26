# Stream 3 — Document Intelligence & Routing Architecture Proposal

```
Epic              1 — Intelligent Document Intake
Stream            3 — Document Intelligence & Routing
Architecture      v3.0 (Platform FROZEN)
────────────────────────────────────────────────────
Status            PROPOSED (Phase 0)
```

## 1. Executive Summary

После Stream 1 (Document Lifecycle) и Stream 2 (Processing Pipeline)
документ доходит до состояния ANALYZED с заполненным profile:
тип, извлечённые поля, confidence, ссылка на KnowledgeRevision.

Stream 3 отвечает на вопрос:

**"Что делать с документом после анализа?"**

Ответ — Routing: на основе типа документа, извлечённых данных и confidence
система принимает решение о бизнес-действии и направляет документ
в соответствующий продукт (Accounting, Deal workflow, etc.).

Routing — Product Layer. Никаких изменений в Knowledge Layer или Platform.

## 2. Document Intelligence Model

### 2.1 Analyzed Document (что есть на входе)

После Stream 2 каждый документ имеет:

```python
Document.profile = {
    "confidence": 0.95,           # общая confidence pipeline
    "document_type": "invoice",
    "ocr_quality": 0.97,
    "classification_confidence": 0.99,
    "extraction_confidence": 0.93,
    "knowledge_revision_id": "rev-xxx",
    "needs_review": False,
    # Extracted fields (from pipeline result)
    "fields": {
        "supplier": "ООО Ромашка",
        "amount": "1000.00",
        "vat": "200.00",
        "date": "01.01.2024",
        "invoice_number": "INV-001",
    }
}
```

### 2.2 Intelligence Model (v1)

Расширение profile после routing:

```python
Document.intelligence = {
    "routing_decision": "send_to_accounting",
    "routing_confidence": 0.95,
    "business_destination": "accounting",
    "business_entity_id": "acc-period-2024-q1",
    "matched_entities": {
        "supplier_id": "counterparty-123",
        "contract_id": "contract-456",
    },
    "needs_approval": False,
    "decided_at": "...",
}
```

### 2.3 Product: понятие

Product — целевая бизнес-область, в которую направляется документ.
Примеры для v1:

- **accounting** — счета, акты, банковские выписки
- **deal** — договоры, допсоглашения
- **crm** — карточки клиентов, доверенности
- **compliance** — паспорта, лицензии

Product — Product Layer concept, не Platform.

## 3. Decision Lifecycle

### 3.1 Полный lifecycle документа (c учётом Stream 3)

```
UPLOADED
    ↓
ACCEPTED
    ↓
PROCESSING
    ↓
ANALYZED  ← Stream 2 завершён
    ↓
EVALUATING  ← Stream 3: routing decision in progress
    ↓
DECIDED     ← routing decision made
    ↓
ROUTED      ← document sent to destination product
    ↓
ARCHIVED
```

### 3.2 Error states

| State | Meaning |
|-------|---------|
| ROUTING_FAILED | No matching routing rule |
| NEEDS_REVIEW | Confidence too low for auto-route |
| MANUAL_OVERRIDE | User overrode routing decision |

### 3.3 Состояния Routing Engine

```
PENDING → EVALUATING → DECIDED → ROUTED
                          ↓
                      FAILED
```

## 4. Routing Engine

### 4.1 Domain Model

```python
@dataclass
class RoutingRule:
    rule_id: str
    name: str
    document_type: str           # "invoice" | "contract" | ...
    condition: str               # Python expression or simple condition
    destination: str             # "accounting" | "deal" | "crm" | ...
    priority: int
    min_confidence: float        # 0.0 - 1.0
    needs_approval: bool
    active: bool

@dataclass
class RoutingDecision:
    decision_id: str
    document_id: str
    rule_id: str | None
    destination: str
    confidence: float
    status: str                  # "DECIDED" | "ROUTED" | "FAILED"
    matched_entities: dict
    needs_approval: bool
    created_at: datetime
    routed_at: datetime | None

@dataclass
class RoutingResult:
    decision_id: str
    destination: str
    matched: bool
    rule: str | None
    confidence: float
```

### 4.2 Routing Rules (v1 — hardcoded)

```python
ROUTING_RULES = [
    RoutingRule(
        name="Invoice to Accounting",
        document_type="invoice",
        condition="extraction_confidence >= 0.7",
        destination="accounting",
        priority=10,
        min_confidence=0.7,
        needs_approval=False,
    ),
    RoutingRule(
        name="Contract to Deal",
        document_type="contract",
        condition="classification_confidence >= 0.6",
        destination="deal",
        priority=10,
        min_confidence=0.6,
        needs_approval=True,  # contracts may need manual review
    ),
    RoutingRule(
        name="Act to Accounting",
        document_type="act",
        condition="extraction_confidence >= 0.7",
        destination="accounting",
        priority=10,
        min_confidence=0.7,
        needs_approval=False,
    ),
    RoutingRule(
        name="Bank statement to Accounting",
        document_type="bank_statement",
        condition="classification_confidence >= 0.6",
        destination="accounting",
        priority=10,
        min_confidence=0.6,
        needs_approval=False,
    ),
    RoutingRule(
        name="Passport to CRM",
        document_type="passport",
        condition="True",
        destination="crm",
        priority=10,
        min_confidence=0.0,
        needs_approval=True,
    ),
    RoutingRule(
        name="Default — manual review",
        document_type="unknown",
        condition="True",
        destination="needs_review",
        priority=0,
        min_confidence=0.0,
        needs_approval=True,
    ),
]
```

### 4.3 Matching Engine

```python
class RoutingEngine:
    def evaluate(self, document: Document) -> RoutingResult:
        profile = document.profile
        doc_type = profile.get("document_type", "unknown")
        confidence = profile.get("confidence", 0.0)

        # Find matching rules for this document type
        candidates = [r for r in ROUTING_RULES
                      if r.document_type == doc_type
                      and r.active
                      and confidence >= r.min_confidence]

        if not candidates:
            # Fallback to default
            default = next(r for r in ROUTING_RULES
                          if r.document_type == "unknown")
            return RoutingResult(
                matched=False,
                destination="needs_review",
                rule=default.name,
                confidence=confidence,
            )

        # Pick highest priority rule
        best = max(candidates, key=lambda r: (r.priority, r.min_confidence))
        return RoutingResult(
            matched=True,
            destination=best.destination,
            rule=best.name,
            confidence=confidence,
            needs_approval=best.needs_approval,
        )
```

## 5. Entity Matching (v1)

### 5.1 Зачем

Routing должен не только определить destination,
но и привязать документ к существующим бизнес-сущностям.

Пример: invoice с supplier = "ООО Ромашка"
→ найти counterparty в системе → привязать document_id.

### 5.2 v1: Simple match

```python
class EntityMatcher:
    def match_counterparty(self, name: str) -> str | None:
        # PostgreSQL: SELECT id FROM counterparties
        #   WHERE name ILIKE %s OR inn = %s
        # Returns first match or None
        pass

    def match_deal(self, contract_number: str) -> str | None:
        # SELECT id FROM deals WHERE contract_number = %s
        pass

    def match_period(self, date: str) -> str | None:
        # SELECT id FROM accounting_periods
        #   WHERE %s BETWEEN start_date AND end_date
        pass
```

### 5.3 No Platform changes

Entity matching queries existing business tables (Product Layer).
No new indexes, no schema changes.
Tables are in the same PostgreSQL database.

## 6. Storage Model

### 6.1 New table: `routing_decisions`

```sql
CREATE TABLE routing_decisions (
    decision_id   TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES document_intake(document_id),
    rule_id       TEXT,
    destination   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'PENDING',
    confidence    REAL NOT NULL DEFAULT 0.0,
    matched_entities JSONB DEFAULT '{}',
    needs_approval BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    routed_at     TIMESTAMP,
    metadata      JSONB DEFAULT '{}'
);
```

### 6.2 Data flow

```
document_intake (profile updated by pipeline)
       |
       | document_id
       v
routing_decisions (decision per routing attempt)
       |
       | destination + matched entities
       v
Business Product (accounting, deal, crm — NOT in this Stream)
```

### 6.3 No Platform changes

- knowledge_revisions: unchanged
- projection_store: unchanged
- document_intake: only profile JSONB updated (no schema change)
- routing_decisions: new Product Layer table

## 7. API Contracts

### 7.1 Evaluate routing

```
POST /documents/{id}/route
  → returns RoutingResult with destination
  → updates document status to DECIDED or ROUTED
```

### 7.2 Get routing decision

```
GET /routing/decisions/{decision_id}
  → full decision details
```

### 7.3 Get document routing status

```
GET /documents/{id}/route
  → current routing decision or null
```

### 7.4 Override routing (manual)

```
POST /routing/decisions/{decision_id}/override
  body: { "destination": "deal" }
  → manual override of routing decision
```

## 8. Events

### 8.1 Event Model

```python
@dataclass
class DocumentEvent:
    event_type: str
    document_id: str
    timestamp: datetime
    data: dict
```

### 8.2 v1 Events

| Event | When | Payload |
|-------|------|---------|
| `document.analyzed` | Stream 2 complete | profile, fields, confidence |
| `routing.decided` | Routing decision made | destination, rule, confidence |
| `document.routed` | Document sent to product | destination, business_entity_id |
| `document.needs_review` | Confidence too low | reason |
| `routing.overridden` | User overrode routing | previous, new destination |

### 8.3 Event storage (v1)

Events stored in `routing_decisions.metadata` JSONB.
No separate event store in v1.

## 9. Service Boundaries

### 9.1 Product Layer (new — this Stream)

```
backend/services/
├── routing/
│   ├── __init__.py
│   ├── engine.py        # RoutingEngine — rule matching
│   ├── matcher.py       # EntityMatcher — counterparty/deal lookup
│   ├── storage.py       # RoutingDecision persistence
│   └── models.py        # RoutingRule, RoutingDecision, RoutingResult
└── events/
    ├── __init__.py
    └── dispatcher.py    # Event emission (v1: log + metadata update)
```

### 9.2 Integration points

```
Pipeline (Stream 2) → Routing (Stream 3):
  • Pipeline completes → triggers routing evaluation
  • Document profile → routing engine input

Routing → Business Products (future, NOT Stream 3):
  • Decision.destination → Accounting module
  • Decision.destination → Deal workflow
  • Decision.destination → CRM

Routing → Knowledge Layer:
  • NO direct integration
  • Knowledge Layer remains unchanged
```

## 10. Test Strategy

### 10.1 Unit Tests

```
✓ Routing rules evaluation (all document types)
✓ Confidence threshold matching
✓ Priority-based rule selection
✓ Fallback to default rule
✓ Entity matching (counterparty, deal, period)
✓ Edge cases: unknown type, missing fields, low confidence
```

### 10.2 Integration Tests

```
✓ POST /documents/{id}/route → returns decision
✓ Document status updated after routing
✓ Routing decision persisted
✓ Override endpoint works
✓ Full flow: ANALYZED → EVALUATING → DECIDED → ROUTED
```

### 10.3 Regression

```
✓ All existing Knowledge capabilities (1033 tests)
✓ All Stream 1 document lifecycle (16 tests)
✓ All Stream 2 pipeline (16 tests)
✓ 0 Platform files changed
✓ 0 Knowledge Layer changes
```

## 11. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Wrong routing rule matches | Document sent to wrong product | Add confidence threshold + manual override |
| Entity matching no match | Document stuck | Route to NEEDS_REVIEW with clear reason |
| Routing too complex in v1 | Over-engineering | Hardcoded rules, no rule engine |
| Business products not ready | Document routed nowhere | Store decision, document stays in DECIDED |
| Pipeline confidence too low | All documents → NEEDS_REVIEW | Tune thresholds per document type |

## 12. Implementation Order

### T1 — Routing Models + Engine

```
Files:
  backend/services/routing/models.py
  backend/services/routing/engine.py

Deliverable:
  RoutingRule model, RoutingDecision model
  RoutingEngine with hardcoded rules
  Unit tests for rule matching
```

### T2 — Entity Matching

```
Files:
  backend/services/routing/matcher.py

Deliverable:
  Counterparty lookup by name/INN
  Deal lookup by contract number
  Accounting period lookup by date
```

### T3 — Routing API

```
Files:
  backend/api/routes/routing.py
  backend/services/routing/storage.py

Deliverable:
  POST /documents/{id}/route
  GET /documents/{id}/route
  GET /routing/decisions/{decision_id}
```

### T4 — Manual Override + Events

```
Files:
  backend/services/events/dispatcher.py

Deliverable:
  POST /routing/decisions/{id}/override
  Event emission (metadata-based)
  NEEDS_REVIEW flow
```

### T5 — Integration Tests

```
Files:
  backend/tests/integration/test_routing.py

Deliverable:
  Full routing integration tests
  Regression suite
```

## 13. Architectural Invariants

```
1. Platform unchanged           — Knowledge Layer + Domain frozen
2. Routing is Product Layer     — NOT part of Knowledge v3.0
3. Document stays central       — all routing is document-centric
4. Decisions are observable     — stored in routing_decisions table
5. Override is always possible  — manual intervention supported
6. No AI dependency in v1       — rule-based routing only
```

## 14. GO / NO-GO Criteria

**GO** if all of the following hold:

1. ✅ Routing can be implemented as pure Product Layer
2. ✅ Platform remains frozen (0 changes)
3. ✅ Knowledge Layer unchanged
4. ✅ Document->Routing->Business flow is deterministic
5. ✅ Manual override is supported

**NO-GO** if any of:

1. ❌ Requires Platform component change
2. ❌ Requires Knowledge Layer modification
3. ❌ Requires AI/ML for v1 routing
4. ❌ Creates dependency between Knowledge and Business products

```
Phase 0 verdict:

  Product Layer:      ✅ Routing Engine + Entity Matching
  Platform changes:   0 (predicted)
  Knowledge changes:  0
  ML dependency:      None (rule-based v1)
  GO recommendation:  ✅ STRONG GO
```
