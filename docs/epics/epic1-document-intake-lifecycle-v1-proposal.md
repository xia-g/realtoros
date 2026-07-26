# Document Intake & Lifecycle v1 — Phase 0 Proposal

```
Status            PROPOSED (Phase 0)
Epic              1 — Intelligent Document Intake
Stream            1 — Document Intake & Lifecycle
──────────────────────────────────────────────
Architecture      v3.0
Baseline
──────────────────────────────────────────────
Date              2026-07-21
```

## Architectural Objective

Establish Document as the primary entity of the Product Layer,
with a managed lifecycle from upload to archival.

Document becomes the input layer for Knowledge Platform.
PDF is one source — not the central object.

## 1. Document Lifecycle

```
UPLOADED
    │  file received, not yet validated
    ▼
ACCEPTED
    │  format valid, checksum passed, storage written
    ▼
PROCESSING
    │  OCR / classification / extraction in progress
    ▼
ANALYZED
    │  all pipeline steps complete
    ▼
ROUTED
    │  sent to Accounting / Deal / CRM
    ▼
ARCHIVED
```

### States detail

| State | Meaning | Entry condition | Exit condition |
|-------|---------|----------------|----------------|
| UPLOADED | File received by API | HTTP request received | File validated + stored |
| ACCEPTED | File accepted, storage written | Validation passed | Pipeline started |
| PROCESSING | OCR/analysis in progress | Pipeline triggered | All steps complete |
| ANALYZED | Analysis complete, Knowledge exists | Pipeline finished | Routing decision made |
| ROUTED | Sent to downstream product | Routing rule matched | Retention period met |
| ARCHIVED | No longer active | Business rule triggered | — (terminal) |

### Error states

| State | Meaning |
|-------|---------|
| REJECTED | File format not supported |
| FAILED | Processing error (OCR failure, etc.) |
| NEEDS_REVIEW | Quality below threshold |

## 2. Canonical Document Model

```
Document
├── document_id:          UUID (primary key)
├── organization_id:      str
├── uploaded_by:          str
├── uploaded_at:          datetime
├── status:               str (lifecycle state)
├── pipeline_stage:       str (current pipeline step)
│
├── file (source)
│   ├── storage_uri:      str
│   ├── mime_type:        str
│   ├── page_count:       int
│   ├── size_bytes:       int
│   ├── checksum:         str
│   └── original_filename: str
│
├── metadata (optional before OCR)
│   ├── language:         str | null
│   ├── source:           str ("upload" | "email" | "api" | "scan")
│   ├── owner:            str | null
│   ├── linked_deal:      str | null
│   └── linked_period:    str | null
│
├── profile (populated after analysis)
│   ├── confidence:       float
│   ├── document_type:    str | null
│   ├── classification_confidence: float | null
│   ├── ocr_quality:      float | null
│   ├── needs_review:     bool
│   └── warnings:         list[str]
│
└── relations
    ├── source_document_id: str | null  (parent document for archives)
    └── knowledge_revision_ids: list[str]
```

## 3. Events (state transitions)

| Event | From | To | Trigger |
|-------|:----:|:--:|---------|
| `document.uploaded` | — | UPLOADED | API receives file |
| `document.accepted` | UPLOADED | ACCEPTED | Validation OK |
| `document.rejected` | UPLOADED | REJECTED | Validation fails |
| `document.pipeline_started` | ACCEPTED | PROCESSING | Pipeline triggered |
| `document.analyzed` | PROCESSING | ANALYZED | All pipeline steps done |
| `document.pipeline_failed` | PROCESSING | FAILED | Error in any step |
| `document.needs_review` | PROCESSING | NEEDS_REVIEW | Quality < threshold |
| `document.routed` | ANALYZED | ROUTED | Routing rule matched |
| `document.archived` | ROUTED | ARCHIVED | Retention rule triggered |

## 4. Document vs Knowledge Boundary

```
Document Layer (new)
├── File storage, validation, lifecycle
├── OCR, classification, extraction orchestration
├── Document Profile (quality metrics)
└── Routing to downstream products

Knowledge Layer (v3.0, existing)
├── KnowledgeRevision (created after analysis)
├── KnowledgeSnapshot (graph, provenance, explanation)
├── Explorer, Timeline, Diff, Search, Traversal, etc.
└── Trust, Governance, Recovery

Boundary:
  Document.intake → KnowledgeRevision.revision
  via source_document_id
```

## 5. Platform Impact Assessment

| Component | Changed? | Reason |
|-----------|:--------:|--------|
| Domain | ❌ | Document is Product Layer, not Domain |
| KnowledgeRevision | ❌ | Linked via source_document_id |
| KnowledgeSnapshot | ❌ | Unchanged |
| Repository Protocol | ❌ | Document repo is separate |
| Bootstrap | ❌ | Document lifecycle is product, not platform |
| Existing routes | ❌ | New routes, not modification |

**Prediction: Platform files changed = 0**

Document model lives in the Product Layer.
New repository for documents (not Platform).
New API routes for upload/lifecycle.

## 6. Key Design Decisions for v1

### 6.1. Storage

Files stored on disk (existing pattern) with metadata in PostgreSQL.
New table: `documents` (document_id PK, status, metadata, profile JSONB).

### 6.2. Existing OCR integration

Current OCR API (port 8001) becomes a pipeline step.
Document orchestrator calls OCR, stores result, updates status.

### 6.3. Pipeline orchestration

Event-driven: each step completion triggers the next.
Status transitions logged for audit.

### 6.4. Downstream transparency

After analysis, downstream products (Accounting, CRM) receive
Document Profile + Knowledge Revision ID.
They never read raw files.

## 7. Validation Plan

```
□ Document model defined with all lifecycle states
□ Upload → ACCEPTED works
□ Pipeline processing → ANALYZED works
□ Document Profile populated after analysis
□ Error states REJECTED / FAILED / NEEDS_REVIEW work
□ Routing to downstream works
□ Knowledge revision linked correctly
□ Existing Knowledge capabilities compatible
□ Tests cover all state transitions
```

## Phase 0 Verdict

```
Document Intake & Lifecycle v1

Product Layer:          ✅ (not Platform)
Platform changes:       0 (predicted)
Knowledge integration:  via source_document_id
Storage:                New documents table (Product, not Platform)
Execution:              Event-driven pipeline
```
