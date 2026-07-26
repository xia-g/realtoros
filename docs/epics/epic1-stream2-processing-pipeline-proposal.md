# Stream 2 — Document Processing Pipeline Architecture Proposal

```
Epic              1 — Intelligent Document Intake
Stream            2 — Document Processing Pipeline
Architecture      v3.0 (Platform FROZEN)
────────────────────────────────────────────────────
Status            PROPOSED
```

## 1. Executive Summary

Цель Stream 2 — построить production-ready pipeline обработки документов
поверх Document Lifecycle (Stream 1).

OCRNode уже работает (port 8001). Задача — интегрировать его как pipeline step,
добавить Quality Assessment, Classification, Entity Extraction и Knowledge Binding.

Никаких изменений в Frozen Platform v3.0.

## 2. Domain Model

### 2.1 ProcessingPipeline

Контейнер для pipeline steps, orchestrator.

```python
@dataclass
class ProcessingPipeline:
    pipeline_id: str
    document_id: str
    status: PipelineStatus     # PENDING | RUNNING | COMPLETED | FAILED
    steps: list[PipelineStep]
    created_at: datetime
    completed_at: datetime | None
```

### 2.2 PipelineStep

Отдельный шаг обработки.

```python
@dataclass
class PipelineStep:
    step_type: str            # "ocr" | "quality" | "classification" | "extraction" | "knowledge_binding"
    status: StepStatus        # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    started_at: datetime | None
    completed_at: datetime | None
    result: dict              # step-specific output
    error: str | None
```

### 2.3 Step Results

```python
@dataclass
class OCRResult:
    raw_text: str
    confidence: float         # 0.0 - 1.0
    language: str | None
    page_count: int
    warnings: list[str]

@dataclass
class QualityResult:
    ocr_confidence: float
    overall_score: float
    missing_pages: int
    low_quality_regions: list
    needs_review: bool
    warnings: list[str]

@dataclass
class ClassificationResult:
    document_type: str        # "invoice" | "contract" | "bank_statement" | ...
    confidence: float
    alternatives: list[tuple[str, float]]

@dataclass
class ExtractionResult:
    fields: dict              # type-specific: {supplier, amount, vat, date, ...}
    confidence: float
    warnings: list[str]

@dataclass
class KnowledgeBindingResult:
    knowledge_revision_id: str | None
    snapshot: KnowledgeSnapshot | None
    confidence: float
```

### 2.4 Document Profile (расширение)

После pipeline Document Profile пополняется:

```python
profile = {
    "confidence": 0.95,           # общая
    "document_type": "invoice",
    "ocr_quality": 0.97,
    "classification": 0.99,
    "extraction": 0.93,
    "language": "ru",
    "needs_review": False,
    "warnings": [],
    "knowledge_revision_id": "rev-xxx",
}
```

## 3. Lifecycle Model

### 3.1 Document Lifecycle + Pipeline

```
Document Lifecycle           Processing Pipeline
─────────────────           ───────────────────
UPLOADED
    ↓
ACCEPTED  ──────────────►   PENDING
                                ↓
                              RUNNING
                            ├── OCR step
                            ├── Quality step
                            ├── Classification step
                            ├── Extraction step
                            └── Knowledge Binding step
                                ↓
    ◄────────────────────   COMPLETED (or FAILED)
ANALYZED
    ↓
READY
    │ profile populated
    ↓
ROUTED
    ↓
ARCHIVED
```

### 3.2 State Transitions в Pipeline

```
PENDING → RUNNING       (pipeline triggered)
RUNNING → RUNNING       (step completed, next step starts)
RUNNING → COMPLETED     (all steps done)
RUNNING → FAILED        (irrecoverable error)
RUNNING → PARTIAL       (some steps failed, others completed)
```

### 3.3 Error Handling

- **Step failure**: mark step FAILED, continue pipeline with WARNING status
- **Pipeline failure**: set Document status = FAILED, log details
- **Retry**: change Document status back to ACCEPTED, pipeline restarts
- **Needs review**: set Document status = NEEDS_REVIEW, pause pipeline

## 4. Service Boundaries

### 4.1 Product Layer (new — this Stream)

```
backend/services/processing/
├── __init__.py
├── pipeline.py              # Pipeline orchestrator
├── steps/
│   ├── __init__.py
│   ├── ocr_step.py          # OCRNode integration
│   ├── quality_step.py      # OCR quality assessment
│   ├── classification_step.py  # Document type detection
│   ├── extraction_step.py   # Entity extraction
│   └── knowledge_step.py    # Knowledge creation binding
├── storage.py               # Pipeline + step persistence
└── models.py                # Pipeline domain model
```

### 4.2 Knowledge Layer (v3.0 — existing, unchanged)

```
application/knowledge_persistence/
  └── KnowledgeRevision, KnowledgeSnapshot, RevisionBuilder

application/capabilities/
  └── Consistency, Audit, Trust, Governance, Recovery
```

### 4.3 Integration Points

```
Pipeline → Knowledge Layer:
  • Knowledge_step creates KnowledgeRevision via existing repo
  • Pipeline uses source_document_id → Knowledge link

Pipeline → Document:
  • Pipeline reads Document from DocumentRepository
  • Pipeline updates Document profile + status

Pipeline → OCR:
  • ocr_step calls OCRNode API (port 8001)
  • Step stores result in PipelineStep.result
```

## 5. Storage Boundary

### 5.1 New Table: `processing_pipelines`

```sql
CREATE TABLE processing_pipelines (
    pipeline_id     TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES document_intake(document_id),
    status          TEXT NOT NULL DEFAULT 'PENDING',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMP,
    metadata        JSONB DEFAULT '{}'
);
```

### 5.2 New Table: `pipeline_steps`

```sql
CREATE TABLE pipeline_steps (
    step_id         TEXT PRIMARY KEY,
    pipeline_id     TEXT NOT NULL REFERENCES processing_pipelines(pipeline_id),
    step_type       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    result          JSONB DEFAULT '{}',
    error           TEXT
);
```

### 5.3 No Platform Changes

- knowledge_revisions: unchanged
- document_intake: only profile JSONB updated (no schema change)
- projection_store: unchanged
- No new Platform-level indexes or relations

## 6. API Contracts

### 6.1 Trigger Pipeline (из Document API)

```
POST /documents/{id}/process
  → starts pipeline, returns pipeline_id
  → status: 202 Accepted
```

### 6.2 Pipeline Status

```
GET /processing/pipelines/{pipeline_id}
  → pipeline with all step statuses
```

### 6.3 List Documents by Processing Status

```
GET /documents?status=ANALYZED
  → already exists from Stream 1
```

### 6.4 Trigger Specific Step (for debugging)

```
POST /processing/pipelines/{pipeline_id}/steps/{step_type}/retry
  → restart a failed step
```

## 7. OCRNode Integration

### 7.1 Current OCRNode

```
Port:   8001
API:    /ocr/document (POST form: file + lang)
Output: raw text, confidence, pages
Status: production, Tesseract 5 rus+eng, CPU-only
```

### 7.2 Integration Contract

```python
class OCRStep:
    """Call OCRNode API, store result."""

    def execute(self, document: Document) -> OCRResult:
        # 1. Read file from storage_uri
        # 2. POST to OCRNode: /ocr/document
        # 3. Parse response
        # 4. Return OCRResult

    def validate(self, result: OCRResult) -> QualityResult:
        # 1. Check confidence threshold
        # 2. Check page count matches
        # 3. Return QualityResult
```

### 7.3 Quality Thresholds (v1)

| Metric | Threshold | Action |
|--------|-----------|--------|
| OCR confidence | ≥ 0.90 | Continue |
| OCR confidence | 0.70 - 0.89 | NEEDS_REVIEW |
| OCR confidence | < 0.70 | FAILED |
| Page count mismatch | > 0 | WARNING |

## 8. Classification Strategy (v1)

### 8.1 Approach: Rule-based + Keyword Matching

Не ML в v1. Достаточно эвристик:

```python
class RuleBasedClassifier:
    PATTERNS = {
        "invoice": {
            "keywords": ["счет", "invoice", "счет-фактура", "invoice number"],
            "expected_fields": ["supplier", "amount", "vat", "date"],
        },
        "contract": {
            "keywords": ["договор", "contract", "соглашение", "agreement"],
            "expected_fields": ["parties", "date", "amount", "terms"],
        },
        "bank_statement": {
            "keywords": ["выписка", "bank statement", "операции", "transaction"],
            "expected_fields": ["transactions", "balance"],
        },
        "act": {
            "keywords": ["акт", "act", "acceptance", "выполненных работ"],
            "expected_fields": ["parties", "date", "amount", "service"],
        },
    }
```

Classification confidence = keyword match ratio.

### 8.2 Future

Replace with ML classifier when data volume justifies it.
Pipeline step is pluggable — swap implementation only.

## 9. Extraction Strategy (v1)

### 9.1 Approach: Rule-based + OCR regex

```python
class InvoiceExtractor:
    """Extract fields from OCR text using patterns."""

    PATTERNS = {
        "supplier": r"(?:поставщик|supplier|продавец)[:\s]+(.+)",
        "invoice_number": r"(?:№|номер|invoice\s+#?)[:\s]*(\S+)",
        "amount": r"(?:сумма|total|amount|итого)[:\s]*([\d\s.,]+)",
        "vat": r"(?:ндс|vat|налог)[:\s]*([\d\s.,]+)",
        "date": r"\d{2}[./]\d{2}[./]\d{4}",
    }
```

Schema is type-specific (different patterns for invoice vs contract).

### 9.2 Quality

- Extraction confidence = percentage of required fields found
- If < 70% required fields → pipeline WARNING
- Missing fields stored in extraction warnings

## 10. Knowledge Binding

### 10.1 Integration

После extraction pipeline создаёт KnowledgeRevision:

```python
class KnowledgeBindingStep:
    def execute(self, document: Document,
                extraction: ExtractionResult,
                classification: ClassificationResult) -> KnowledgeBindingResult:
        # 1. Build KnowledgeGraph from extracted entities
        # 2. Build KnowledgeSnapshot with provenance
        # 3. Use RevisionBuilder to create revision
        # 4. Save via existing KnowledgeRevisionRepository
        # 5. Link document → knowledge_revision_id
```

### 10.2 Invariant

Pipeline creates **one** KnowledgeRevision per processing pass.
Recovery would create additional revisions (existing v3.0 mechanism).

## 11. Test Strategy

### 11.1 Unit Tests

```
✓ Pipeline state machine (PENDING → COMPLETED)
✓ Step orchestration (sequential execution)
✓ Error handling (step failure → pipeline FAILED)
✓ Retry logic (FAILED step → retry)
✓ Classification rules (keyword matching)
✓ Extraction patterns (regex per type)
```

### 11.2 Integration Tests

```
✓ Full pipeline: ACCEPTED → pipeline → ANALYZED
✓ Pipeline updates Document profile
✓ KnowledgeRevision created after pipeline
✓ OCRNode integration (mock or real)
✓ Document status transitions correct
```

### 11.3 Regression

```
✓ All existing Knowledge layer capabilities (1033 tests)
✓ All Stream 1 Document lifecycle tests (16 tests)
✓ 0 Platform files changed
```

## 12. Implementation Order

### T1 — Pipeline Domain Model + State Machine

```
Files: 
  backend/services/processing/models.py
  backend/services/processing/pipeline.py

Deliverable:
  Pipeline orchestrator with step execution
  State transitions (PENDING → COMPLETED)
  Storage (pipeline + step persistence)
```

### T2 — OCR Adapter + Quality Step

```
Files:
  backend/services/processing/steps/ocr_step.py
  backend/services/processing/steps/quality_step.py

Deliverable:
  OCRNode API integration
  Quality assessment with thresholds
```

### T3 — Classification Step

```
Files:
  backend/services/processing/steps/classification_step.py

Deliverable:
  Rule-based classifier
  Document type detection
  Profile update
```

### T4 — Extraction Step

```
Files:
  backend/services/processing/steps/extraction_step.py

Deliverable:
  Type-specific extraction
  Extraction confidence
```

### T5 — Knowledge Binding

```
Files:
  backend/services/processing/steps/knowledge_step.py

Deliverable:
  KnowledgeRevision creation
  Document → Knowledge link
```

### T6 — Pipeline API

```
Files:
  backend/api/routes/processing.py

Deliverable:
  POST /documents/{id}/process
  GET /processing/pipelines/{pipeline_id}
  Step retry
```

### T7 — Integration Tests

```
Files:
  backend/tests/integration/test_processing_pipeline.py

Deliverable:
  Full pipeline integration
  OCR mock tests
  Knowledge binding verification
  Regression suite
```

## 13. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| OCR quality too low | Pipeline always FAILS | Tune thresholds per document type |
| Extraction regex fragile | Wrong field values | Add field validation step |
| Pipeline timeout | Document stuck in PROCESSING | Add timeout per step + retry |
| Knowledge revision mismatch | Wrong entities | Validate extraction output before binding |
| Classification wrong | Wrong extraction schema | Allow manual override of type |

## 14. Key Architectural Decisions

### Decision 1: Pipeline as Product Layer

- Not Platform. Not Domain.
- Lives in `backend/services/processing/`
- Uses DocumentRepository and KnowledgeRevisionRepository
- No changes to any Platform component

### Decision 2: OCR as adapter, not core

- OCRNode is an external service called via HTTP
- If OCR changes, only OCR step changes
- Pipeline orchestrator is agnostic to OCR engine

### Decision 3: Classification rule-based in v1

- No ML dependency in v1
- Patterns are good enough for common document types
- Pluggable: swap for ML later without pipeline changes

### Decision 4: One KnowledgeRevision per pipeline run

- Pipeline creates exactly one revision
- Recovery creates additional revisions via v3.0 mechanism
- Document → Knowledge is 1:N (one document, many revisions over time)

## 15. Validation Plan

```
□ Pipeline domain model defined
□ State machine working (PENDING → COMPLETED)
□ OCR step integrates with OCRNode
□ Quality step validates OCR output
□ Classification step detects document type
□ Extraction step extracts fields
□ Knowledge binding creates revision
□ Pipeline updates Document profile
□ Error states (FAILED, PARTIAL, NEEDS_REVIEW) work
□ Retry works
□ All existing tests pass
□ Platform files changed: 0
```
