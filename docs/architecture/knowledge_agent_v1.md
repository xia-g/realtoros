# Knowledge Agent V1

## Overview

The Knowledge Agent is the central orchestrator of the document processing pipeline. It accepts raw files (PDF, DOCX, XLSX, JPG, PNG), routes them through the 5-layer processing stack, and outputs structured business knowledge — clients, properties, deals, documents, and communications — stored in PostgreSQL and surfaced through MCP tools.

```
User / Telegram / API
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│              Knowledge Agent V1                          │
│                                                          │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────┐ │
│  │  File   │  │  OCR   │  │ Class. │  │ Extr.  │  │Res.│ │
│  │ Ing.   │→│ Layer  │→│ Layer  │→│ Layer  │→│Lay.│ │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────┘ │
│                                                          │
│  ┌────────┐  ┌────────┐  ┌────────┐                     │
│  │ Graph  │  │ Store  │  │Review  │                     │
│  │ Layer  │→│  & Link │←│ Workfl.│                     │
│  └────────┘  └────────┘  └────────┘                     │
│                                                          │
└──────────────────────────────────────────────────────────┘
    │
    ▼
PostgreSQL (10 domain tables + 9 pipeline tables)
    │
    ▼
MCP Tools: search_knowledge, get_entity, query_graph, status
```

## Component Architecture

### Agent Structure

```
KnowledgeAgent
├── FileIngestionService     (input validation, format detection)
├── OCRService               (PaddleOCR + Tesseract, per ADR-0004)
├── ClassificationService    (rule → ML → LLM, per ADR-0005)
├── ExtractionService        (pattern → LLM, per ADR-0006)
├── ResolutionService        (exact → fuzzy → embedding → review, per ADR-0007)
├── GraphService             (FK + extraction + AI edges, per ADR-0008)
├── StorageService           (write to domain + pipeline tables)
├── ReviewWorkflow           (Telegram inline keyboard)
├── AIService                (model selection router)
└── MCPService               (expose results via MCP tools)
```

### Module Layout (filesystem)

```
ai/
├── knowledge_agent/
│   ├── __init__.py              # KnowledgeAgent class
│   ├── pipeline.py              # Pipeline orchestrator
│   ├── config.py                # Agent configuration
│   │
│   ├── ingestion/               # File input
│   │   ├── __init__.py
│   │   ├── file_ingestion.py    # Validate, detect, convert
│   │   └── converters.py        # PDF→image, DOCX→text, XLSX→text
│   │
│   ├── ocr/                     # OCR (per ocr_layer.md)
│   │   ├── __init__.py
│   │   ├── preprocessor.py      # Deskew, denoise, CLAHE
│   │   ├── paddle_ocr.py        # PaddleOCR wrapper
│   │   ├── tesseract_fallback.py # Tesseract fallback
│   │   └── pdf_converter.py     # PDF→image via pdf2image
│   │
│   ├── classification/          # Document classifier (per document_classifier.md)
│   │   ├── __init__.py
│   │   ├── rule_classifier.py   # Stage 1: rule-based
│   │   ├── ml_classifier.py     # Stage 2: TF-IDF + SVM
│   │   └── llm_classifier.py    # Stage 3: LLM
│   │
│   ├── extraction/              # Entity extraction (per entity_extraction.md)
│   │   ├── __init__.py
│   │   ├── pattern_extractor.py # Stage 1: regex
│   │   ├── llm_extractor.py     # Stage 2: LLM + Pydantic schemas
│   │   └── merger.py            # Pattern + LLM merge
│   │
│   ├── resolution/              # Entity resolution (per entity_resolution.md)
│   │   ├── __init__.py
│   │   ├── exact_matcher.py     # Stage 1: exact fields
│   │   ├── fuzzy_matcher.py     # Stage 2: pg_trgm + Levenshtein
│   │   ├── embedding_matcher.py # Stage 3: pgvector cosine
│   │   └── scorer.py            # Stage 4: confidence scoring
│   │
│   ├── graph/                   # Knowledge graph (per knowledge_graph.md)
│   │   ├── __init__.py
│   │   ├── fk_builder.py        # FK → graph edges
│   │   ├── extraction_builder.py # Document → graph edges
│   │   ├── ai_builder.py        # Inferred edges
│   │   └── query.py             # Graph query patterns
│   │
│   ├── storage/                 # Database persistence
│   │   ├── __init__.py
│   │   ├── document_store.py    # documents + ocr_results
│   │   ├── entity_store.py      # clients, properties, deals
│   │   ├── pipeline_store.py    # classifications, extractions, resolutions
│   │   └── graph_store.py       # graph_nodes + graph_edges
│   │
│   ├── review/                  # Human review workflow
│   │   ├── __init__.py
│   │   ├── review_queue.py      # pending reviews + assignment
│   │   └── telegram_review.py   # Telegram inline keyboard
│   │
│   ├── mcp/                     # MCP tools
│   │   ├── __init__.py
│   │   ├── tools.py             # MCP tool definitions
│   │   └── queries.py           # Graph + entity queries
│   │
│   └── config.py                # Settings, model selection, thresholds
```

## Processing Pipeline

### End-to-End Flow

```
File Upload
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. INGESTION                                                 │
│                                                              │
│ Input:  PDF | DOCX | XLSX | JPG | PNG                        │
│                                                              │
│ Validate: file type, size (< 50 MB), MIME, password (PDF)    │
│ Detect: single/multi-page, colour/b&w, text layer (PDF)      │
│ Convert: PDF → images (300 DPI), DOCX → text, XLSX → CSV     │
│                                                              │
│ Hash: SHA-256 of raw file → check for duplicates             │
│                                                              │
│ Output: file_hash, file_meta, pages[], raw_text (if native)  │
│                                                              │
│ DB: INSERT INTO documents (status='pending')                  │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. OCR                                                       │
│                                                              │
│ For scanned/image docs only (skip if native DOCX/XLSX):      │
│                                                              │
│ Preprocess: orientation → deskew → denoise → CLAHE           │
│                                                              │
│ Primary: PaddleOCR PP-OCRv4 (det + cls + rec)                │
│          PP-Structure layout analysis (tables, paragraphs)   │
│                                                              │
│ Fallback: Tesseract 5 if PaddleConfidence < 0.6              │
│                                                              │
│ Output: raw_text, confidence, layout JSONB, bboxes[]         │
│                                                              │
│ DB: INSERT INTO ocr_results (status='completed')             │
│     UPDATE documents (status='ocr_done')                      │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. CLASSIFICATION                                            │
│                                                              │
│ Stage 1 — Rule: file ext + MIME + page count + keywords      │
│   Confidence ≥ 0.75 → accept, skip to stage 4                │
│   < 0.75 → proceed to Stage 2                                │
│                                                              │
│ Stage 2 — ML: TF-IDF char n-grams + SVM                     │
│   Confidence ≥ 0.85 → accept                                 │
│   0.60–0.85 → proceed to Stage 3                             │
│   < 0.60 → proceed to Stage 3                                │
│                                                              │
│ Stage 3 — LLM (DeepSeek Flash): full OCR context             │
│   Confidence ≥ 0.80 → accept                                 │
│   < 0.80 → flag for human review                             │
│                                                              │
│ Output: document_type, subtype, confidence, method            │
│                                                              │
│ DB: INSERT INTO document_classifications                     │
│     UPDATE documents (status='classified')                    │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. ENTITY EXTRACTION                                         │
│                                                              │
│ Select prompt template by document_type:                     │
│   passport, receipt          → Qwen Local                    │
│   egrn_extract, power_of_att. → DeepSeek Flash               │
│   sale/agency/rental contract → DeepSeek Pro                  │
│                                                              │
│ Stage 1 — Pattern: regex for phones, passports, INN, dates   │
│   (30-40% of fields, zero cost)                              │
│                                                              │
│ Stage 2 — LLM: typed JSON per Pydantic schemas               │
│   Client, Property, Address, Price, Deal, Date, Organization │
│                                                              │
│ Merge: pattern + LLM → hybrid confidence (boost +0.1)       │
│                                                              │
│ Validate: per-field rules + cross-entity checks              │
│   (price consistency, date chronology, party match)          │
│                                                              │
│ Output: 7 entity schemas with per-field confidence            │
│                                                              │
│ DB: INSERT INTO extracted_entities (extraction_data JSONB)    │
│     Status: auto_accepted / human_review / rejected           │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. ENTITY RESOLUTION                                         │
│                                                              │
│ For each extracted entity (client, property, deal, org):     │
│                                                              │
│ Stage 1 — Exact: phone, passport, cadastral, INN             │
│   Match → return existing ID (confidence 0.99)               │
│                                                              │
│ Stage 2 — Fuzzy: pg_trgm + Levenshtein + Russian Soundex     │
│   Match ≥ 0.85 → return existing ID                          │
│   0.60–0.84 → pass to Stage 3                                │
│                                                              │
│ Stage 3 — Embedding: pgvector cosine (384d)                  │
│   Match ≥ 0.80 → return existing ID                          │
│   < 0.80 → pass to Stage 4                                   │
│                                                              │
│ Stage 4 — Score: multi-signal weighted combination           │
│   ≥ 0.85 → auto-merge (enrich-only for clients/properties)   │
│   0.50–0.84 → human review (Telegram inline keyboard)         │
│   < 0.50 → new entity                                        │
│                                                              │
│ Special: Deals are NEVER auto-merged (too sensitive).        │
│   No match → auto-create new deal.                           │
│   Match → human review for any updates.                      │
│                                                              │
│ Output: resolved_entity_id per extracted entity               │
│                                                              │
│ DB: INSERT INTO entity_resolutions (decision, merge_log)      │
│     If human_review → INSERT INTO resolution_reviews          │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. STORAGE & LINKING                                         │
│                                                              │
│ For each resolved entity:                                    │
│   Existing → enrich (fill missing fields, union tags)        │
│   New → INSERT INTO domain table                             │
│                                                              │
│ Create entity ↔ document links:                              │
│   INSERT INTO graph_edges (extracted_from / mentioned_in)    │
│                                                              │
│ Update document status:                                       │
│   UPDATE documents SET status='completed'                     │
│                                                              │
│ Compute + store embedding:                                   │
│   clients.embedding, properties.embedding                     │
│   (Python, multilingual-e5-small, no pgml)                   │
│                                                              │
│ Output: all domain records updated                           │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. KNOWLEDGE GRAPH                                           │
│                                                              │
│ Build/reconcile graph edges:                                 │
│   FK edges: materialize from domain table foreign keys       │
│   Extraction edges: document → entity, entity ↔ entity       │
│   AI edges (scheduled): same-address, shared-deals           │
│                                                              │
│ Output: graph_nodes + graph_edges populated                   │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
Result: Structured knowledge in PostgreSQL + MCP tools
```

### Pipeline Orchestrator

```python
class KnowledgePipeline:
    """Orchestrates the full document processing pipeline.

    Each stage is async and independently retryable.
    Pipeline state is persisted in documents.status.
    """

    STAGES = [
        ("ingestion", FileIngestionService),
        ("ocr", OCRService),
        ("classification", ClassificationService),
        ("extraction", ExtractionService),
        ("resolution", ResolutionService),
        ("storage", StorageService),
        ("graph", GraphService),
    ]

    async def process_document(
        self,
        file_path: str,
        user_id: UUID,
        metadata: dict | None = None,
    ) -> PipelineResult:
        """Process one document through the full pipeline."""

        # Create document record
        doc = await self.document_store.create(
            file_path=file_path,
            uploaded_by=user_id,
            metadata=metadata or {},
            status="pending",
        )

        # Run pipeline stages
        for stage_name, service_class in self.STAGES:
            try:
                stage_result = await self._run_stage(
                    stage_name, service_class, doc
                )
                if stage_result.needs_human_review():
                    await self.review_queue.enqueue(
                        doc_id=doc.id,
                        stage=stage_name,
                        result=stage_result,
                    )
                    doc.status = f"waiting_review_{stage_name}"
                    return PipelineResult(
                        status="waiting_review",
                        stage=stage_name,
                        document_id=doc.id,
                    )
            except PipelineError as e:
                doc.status = f"failed_{stage_name}"
                await self._log_error(doc.id, stage_name, e)
                return PipelineResult(
                    status="failed",
                    stage=stage_name,
                    error=str(e),
                    document_id=doc.id,
                )

        # Build knowledge graph
        await self.graph_service.build_from_document(doc.id)

        # Mark complete
        doc.status = "completed"
        return PipelineResult(
            status="completed",
            document_id=doc.id,
        )

    async def retry_from_stage(
        self,
        document_id: UUID,
        stage: str,
    ) -> PipelineResult:
        """Retry a failed pipeline from a specific stage."""
        doc = await self.document_store.get(document_id)
        start_index = next(
            i for i, (name, _) in enumerate(self.STAGES)
            if name == stage
        )
        for stage_name, service_class in self.STAGES[start_index:]:
            ...  # run stages from retry point
```

## AI Routing Strategy

### Model Selection by Task

| Task | Model | Complexity | Max Tokens | Priority |
|------|-------|-----------|------------|----------|
| OCR text recognition | PaddleOCR (local) | low | N/A | speed |
| Document classification (Stage 2) | TF-IDF + SVM (local) | low | N/A | speed |
| Document classification (Stage 3) | DeepSeek Flash | medium | 8K input | accuracy |
| Entity extraction (passport, receipt) | Qwen Local | low | 4K input | cost |
| Entity extraction (egrn, power_of_attorney) | DeepSeek Flash | medium | 8K input | accuracy |
| Entity extraction (contracts) | DeepSeek Pro | high | 16K input | accuracy |
| Entity resolution (embeddings) | multilingual-e5-small (local) | low | N/A | speed |
| Human review fallback | ChatGPT | critical | 32K input | reliability |

### Model Router Logic

```python
class AIRouter:
    """Routes AI tasks to the appropriate model based on
    document complexity, cost budget, and availability."""

    ROUTING_TABLE = {
        "ocr": {
            "primary": PaddleOCR,
            "fallback": Tesseract5,
            "fallback_trigger": "confidence < 0.6",
        },
        "classify_rule": {
            "engine": RuleClassifier,
            "cost": "free",
        },
        "classify_ml": {
            "engine": MLClassifier,
            "cost": "50ms_cpu",
            "fallback_trigger": "model_not_trained",
        },
        "classify_llm": {
            "engine": LLMClassifier,
            "model": "deepseek-flash",
            "fallback": "deepseek-pro",
            "fallback_trigger": "timeout > 10s",
        },
        "extract_passport": {
            "engine": LLMExtractor,
            "model": "qwen-local",
            "prompt": "passport_v1",
        },
        "extract_receipt": {
            "engine": LLMExtractor,
            "model": "qwen-local",
            "prompt": "receipt_v1",
        },
        "extract_egrn": {
            "engine": LLMExtractor,
            "model": "deepseek-flash",
            "prompt": "egrn_extract_v1",
        },
        "extract_contract": {
            "engine": LLMExtractor,
            "model": "deepseek-pro",
            "prompt": "sale_contract_v1 / agency_contract_v1 / rental_contract_v1",
        },
        "resolve_embedding": {
            "engine": EmbeddingMatcher,
            "model": "intfloat/multilingual-e5-small",
        },
        "resolve_llm": {
            "engine": LLMResolver,
            "model": "deepseek-flash",
            "fallback": "chatgpt",
            "fallback_trigger": "ambiguous_match > 2 candidates",
        },
    }

    async def route(
        self, task_type: str, context: dict
    ) -> AIResult:
        """Select and invoke the appropriate AI model."""

        route = self.ROUTING_TABLE[task_type]
        engine = route["engine"](**route.get("params", {}))

        try:
            result = await engine.run(context)
            if self._needs_fallback(result, route):
                return await self._run_fallback(route, context)
            return result
        except (TimeoutError, ModelUnavailableError):
            if "fallback" in route:
                return await self._run_fallback(route, context)
            raise
```

### Fallback Cascade (by layer)

| Layer | Primary | Fallback | Last Resort |
|-------|---------|----------|-------------|
| OCR | PaddleOCR | Tesseract 5 | "Cannot read document" |
| Classification | Rule → ML → LLM | — | Manual review |
| Extraction | Pattern → LLM | Pattern-only | Manual extraction |
| Resolution | Exact → Fuzzy → Embedding | ML-only | Manual resolution |
| Graph | FK → Extraction → AI | FK-only | — |

## Confidence Strategy

### Per-Layer Confidence

```
Layer Confidence Flow:
                          ┌─────────────────────────┐
                          │  Overall Document       │
                          │  Confidence             │
                          │  (min of all layers)    │
                          └──────────┬──────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
    ┌──────────────┐       ┌──────────────────┐    ┌──────────────────┐
    │ OCR          │       │ Classification   │    │ Extraction       │
    │ 0.0 – 1.0    │       │ 0.0 – 1.0        │    │ 0.0 – 1.0        │
    │              │       │                  │    │                  │
    │ avg char     │       │ classifier       │    │ per-entity avg   │
    │ confidence   │       │ probability      │    │ (weighted)       │
    └──────────────┘       └──────────────────┘    └──────────────────┘
                                                           │
                                                    ┌──────┴──────┐
                                                    ▼             ▼
                                            ┌────────────┐ ┌──────────┐
                                            │ Resolution │ │Validation│
                                            │ 0.0 – 1.0  │ │ pass/fail│
                                            │            │ │          │
                                            │ multi-     │ │ cross-   │
                                            │ signal avg │ │ entity   │
                                            └────────────┘ └──────────┘
```

### Overall Document Confidence

```python
DOCUMENT_CONFIDENCE = {
    "formula": "min(ocr.confidence, classification.confidence, extraction.confidence)",
    "rationale": "The weakest link determines overall reliability. "
                 "A document with perfect OCR but low extraction confidence "
                 "still needs human review.",
    "thresholds": {
        "auto_complete": 0.85,   # no human review needed
        "partial_review": 0.60,  # review low-confidence entities only
        "full_review": 0.40,     # review entire document
        "reject": 0.0,           # re-upload required
    },
}
```

### Per-Entity Confidence (from extraction)

```python
ENTITY_CONFIDENCE = {
    "formula": "weighted_average(field_confidence * field_weight)",
    "field_weights": {
        "client": {"full_name": 0.30, "phone": 0.25, "passport": 0.25,
                   "email": 0.10, "birth_date": 0.10},
        "property": {"cadastral_number": 0.30, "address": 0.25,
                     "area_total": 0.15, "property_type": 0.15,
                     "rooms": 0.10, "floor": 0.05},
        "deal": {"price": 0.25, "start_date": 0.20, "parties": 0.25,
                 "property": 0.20, "commission": 0.10},
    },
}
```

## Human Review Workflow

### Review Decision Tree

```
Extraction/Resolution Complete
    │
    ├─ Overall confidence ≥ 0.85 ─────────────────→ AUTO: store + graph
    │
    ├─ Overall confidence 0.60–0.84
    │   └─ Entity confidence ≥ 0.85 for all entities → AUTO
    │   └─ Some entities < 0.85
    │       └─ Telegram notification to assigned agent
    │           ├─ Agent confirms → apply
    │           └─ Agent edits → apply with corrections
    │
    ├─ Overall confidence 0.40–0.59
    │   └─ Telegram notification + full detail
    │       ├─ Agent confirms → apply
    │       ├─ Agent edits → apply with corrections
    │       └─ Agent rejects → mark document as failed
    │
    └─ Overall confidence < 0.40
        └─ Reject document → notify agent
            "Пожалуйста, загрузите документ в лучшем качестве"
```

### Telegram Review Interface

```
📄 *Новый документ требует проверки*
───────────────
Файл: договор_купли_продажи.pdf
Тип: sale_contract (ML, точность 87%)

🏠 *Объект недвижимости*
Адрес: г. Москва, ул. Ленина, д. 5, кв. 10
Площадь: 54.2 м² (точность 95%) ✅
Кадастровый: 77:01:0004545:1234 (точность 99%) ✅

👤 *Продавец*
Иванов Иван Иванович (точность 97%) ✅
Телефон: +79161234567 (точность 99%) ✅

👤 *Покупатель*
Петров Пётр Петрович (точность 62%) ⚠️
Телефон: не найден

💰 *Цена: 8 500 000 ₽* (точность 99%) ✅

[✅ Подтвердить] [✏️ Исправить] [❌ Отклонить]
```

### Review Queue Assignment

```python
class ReviewAssignment:
    """Assigns review tasks to agents based on role and load."""

    STRATEGIES = {
        "auto_distribute": {
            "priority": "confidence_ascending",  # lowest first
            "assignment": "round_robin",
            "max_queue_per_agent": 20,
        },
        "role_based": {
            "document_types": {
                "sale_contract": "senior_agent",
                "passport": "any_agent",
                "receipt": "any_agent",
            },
        },
        "escalation": {
            "max_wait_minutes": 30,
            "escalate_to": "manager",
            "notification": "telegram_urgent",
        },
    }
```

## PostgreSQL Integration

### Tables Written by the Knowledge Agent

The Knowledge Agent writes to ALL of the following tables:

| Table | Written By Stage | Purpose |
|-------|-----------------|---------|
| `documents` | Ingestion → Storage | Master document record |
| `ocr_results` | OCR → Storage | OCR text + layout + confidence |
| `document_classifications` | Classification | Type + subtype + method |
| `classification_training_log` | Classification | ML training samples |
| `extracted_entities` | Extraction | Entity data + validation |
| `entity_resolutions` | Resolution | Match decisions + signals |
| `resolution_reviews` | Review Workflow | Human review queue |
| `graph_nodes` | Graph | Unified entity registry |
| `graph_edges` | Graph | Typed relationships |
| `clients` | Storage | Resolved clients |
| `properties` | Storage | Resolved properties |
| `deals` | Storage | Resolved deals |

### Document Lifecycle Status

```
pending → ingesting → ingested
                     → ocr_pending → ocr_processing → ocr_done
                                                      → ocr_failed (→ retry)
                     → classify_pending → classify_processing → classified
                                                               → classify_failed
                     → extract_pending → extract_processing → extracted
                                                             → extract_failed
                     → resolve_pending → resolve_processing → resolved
                                                             → resolve_failed
                                                             → waiting_review
                     → graph_pending → graph_processing → graphed
                                                        → graph_failed
                     → completed
                     → failed (terminal)
```

### Integration with Domain Tables

```
documents (master record, one row per file)
    │
    ├── ocr_results (one row per document_id)
    │
    ├── document_classifications (one row)
    │
    ├── extracted_entities (one row, extraction_data JSONB)
    │
    ├── entity_resolutions (one per extracted entity)
    │   └── resolution_reviews (if human review needed)
    │
    ├── graph_edges (extracted_from / mentioned_in)
    │
    ├── clients (0..N — resolved from document)
    ├── properties (0..1 — resolved from document)
    └── deals (0..1 — resolved from document)
             └── deal_participants (linked to resolved clients)
```

## Error Handling

### Retry Strategy

| Error | Retry? | Max Retries | Backoff | Next Action |
|-------|--------|-------------|---------|-------------|
| OCR timeout (> 30s per page) | Yes | 3 | exponential 5s/15s/45s | Tesseract fallback |
| LLM timeout | Yes | 2 | exponential 3s/9s | Lower model tier |
| LLM invalid JSON | Yes | 1 | immediate | Use pattern-only |
| ML model not trained | No | N/A | N/A | Skip to Stage 3 LLM |
| Database connection lost | Yes | 3 | exponential 1s/5s/15s | Queue for retry |
| File corrupted | No | N/A | N/A | "File corrupted" error |
| Unsupported format | No | N/A | N/A | "Format not supported" |

### Error Taxonomy

```python
class KnowledgeAgentError(Exception):
    """Base error for Knowledge Agent."""

class FileIngestionError(KnowledgeAgentError):
    """File too large, corrupted, or unsupported format."""

class OCRProcessingError(KnowledgeAgentError):
    """OCR failed on all pages, including Tesseract fallback."""

class ClassificationError(KnowledgeAgentError):
    """All 3 classification stages failed."""

class ExtractionError(KnowledgeAgentError):
    """Pattern + LLM extraction failed. No fields extracted."""

class ResolutionError(KnowledgeAgentError):
    """All 4 resolution stages failed. Entity cannot be resolved."""

class StorageError(KnowledgeAgentError):
    """Database write failed. Pipeline state may be inconsistent."""

class ReviewTimeoutError(KnowledgeAgentError):
    """Human review not completed within max_wait_minutes."""
```

### Idempotency

Each document is identified by SHA-256 hash of the raw file. If a file with the same hash already exists in the system:

```python
DUPLICATE_HANDLING = {
    "status": "completed",
    "action": "return existing result",
    "note": "Документ уже загружен ранее ({date}, {user})",
    "reprocess": False,  # no automatic reprocessing
}
```

Manual re-processing is available via MCP tool: `reprocess_document(document_id)`

### Pipeline Recovery

```python
PIPELINE_RECOVERY = {
    "failed_ocr": "retry_ocr",
    "failed_classification": "retry_classification",
    "failed_extraction": "retry_extraction",
    "failed_resolution": "retry_resolution",
    "partial_extraction": "store_partial_review_required",
    "db_write_error": "queue_for_retry_max_3_times",
    "timeout": "retry_with_timeout_increase",
}
```

## MCP Integration

### MCP Tools Exposed

The Knowledge Agent exposes the following tools via the MCP server:

```python
MCP_TOOLS = {
    # ── Document processing ──
    "process_document": {
        "description": "Upload and process a document through the full pipeline",
        "params": {
            "file_path": "str (absolute path to file)",
            "user_id": "UUID",
        },
        "returns": {
            "document_id": "UUID",
            "status": "processing | waiting_review | completed | failed",
            "estimated_time_seconds": "int",
        },
    },

    "get_document_status": {
        "description": "Check processing status of a document",
        "params": {"document_id": "UUID"},
        "returns": {
            "status": "str",
            "progress": {"ocr", "classification", "extraction",
                        "resolution", "graph"},
            "overall_confidence": "float",
            "needs_review": "bool",
        },
    },

    # ── Entity queries ──
    "search_clients": {
        "description": "Search clients by name, phone, or passport",
        "params": {
            "query": "str",
            "fuzzy": "bool (default: true)",
        },
        "returns": [{"id", "full_name", "phone", "confidence"}],
    },

    "search_properties": {
        "description": "Search properties by address or cadastral number",
        "params": {
            "query": "str",
            "fuzzy": "bool (default: true)",
        },
        "returns": [{"id", "address", "cadastral_number", "confidence"}],
    },

    # ── Graph queries ──
    "get_entity_neighborhood": {
        "description": "Find all entities connected to this one",
        "params": {
            "entity_type": "client | property | deal",
            "entity_id": "UUID",
            "max_depth": "int (default: 2)",
        },
        "returns": {
            "nodes": [{"type", "label", "id"}],
            "edges": [{"type", "source", "target", "properties"}],
        },
    },

    "find_path": {
        "description": "Find shortest path between two entities",
        "params": {
            "from_type": "str",
            "from_id": "UUID",
            "to_type": "str",
            "to_id": "UUID",
            "max_depth": "int (default: 6)",
        },
        "returns": {
            "path": [{"type", "label", "edge_type"}],
            "depth": "int",
        },
    },

    # ── Review worklow ──
    "get_pending_reviews": {
        "description": "List pending human review tasks",
        "params": {
            "assigned_to": "UUID | None (None = all)",
            "limit": "int (default: 10)",
        },
        "returns": [{"review_id", "document_id", "stage", "priority"}],
    },

    "resolve_review": {
        "description": "Submit a review decision",
        "params": {
            "review_id": "UUID",
            "decision": "confirm | edit | reject",
            "corrections": "dict | None",
        },
        "returns": {"status": "resolved", "entity_ids": ["UUID"]},
    },

    "reprocess_document": {
        "description": "Re-process a failed or rejected document",
        "params": {
            "document_id": "UUID",
            "from_stage": "ingestion | ocr | classification | extraction | resolution",
        },
        "returns": {"status": "processing", "document_id": "UUID"},
    },
}
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Single page OCR (CPU) | < 5 sec | PaddleOCR, 300 DPI |
| Classification (Stage 1+2) | < 100 ms | Rule + ML, no LLM |
| Classification (Stage 3) | < 5 sec | DeepSeek Flash |
| Extraction (passport) | < 5 sec | Qwen Local |
| Extraction (contract) | < 20 sec | DeepSeek Pro |
| Resolution per entity | < 200 ms | Exact + Fuzzy + Embedding |
| Graph build per document | < 1 sec | FK + extraction edges |
| End-to-end (simple) | < 20 sec | Passport, receipt |
| End-to-end (complex) | < 60 sec | Sale contract, 10 pages |
| Throughput | 100 docs/hour | Single CPU agent |
| Human review response | < 30 min | Telegram notification |

## File Format Handling

| Format | Handler | OCR Needed? | Native Text? |
|--------|---------|-------------|--------------|
| PDF (scanned) | pdf2image → 300 DPI PNG | Yes | No |
| PDF (text layer) | PyMuPDF (fitz) direct extract | No | Yes |
| DOCX | python-docx extract paragraphs | No | Yes |
| XLSX | openpyxl extract cells → CSV | No | Yes |
| JPG/PNG | OpenCV read → PaddleOCR | Yes | No |

**Format detection:** python-magic (libmagic bindings) on file content, not extension.

## Related Documentation

- `docs/architecture/ocr_layer.md` — OCR subsystem (PaddleOCR + Tesseract)
- `docs/architecture/document_classifier.md` — Classification subsystem
- `docs/architecture/entity_extraction.md` — Entity extraction subsystem
- `docs/architecture/entity_resolution.md` — Entity resolution subsystem
- `docs/architecture/knowledge_graph.md` — Knowledge graph subsystem
- `docs/architecture/audit_v1.md` — Architecture audit and known issues
- `docs/adr/0004-ocr-layer-paddleocr.md` through `docs/adr/0010-soft-delete-and-audit.md`
- `docs/domain/domain_model.md` — Core domain entities
- `docs/domain/database_schema_v1.md` — Database schema
- `docs/development_rules.md` — AI model selection guidelines
- `docs/project_status.md` — Current project status
