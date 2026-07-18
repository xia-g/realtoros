# Knowledge Processing Runtime

## Overview

The Knowledge Processing Runtime is the concrete execution engine for the document pipeline. It manages document lifecycle, stage execution with retry, confidence computation, human review orchestration, and atomic commit of extracted knowledge into PostgreSQL.

```
User / API / MCP / Telegram
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│                 Knowledge Processing Runtime                   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────┐  Pipeline Lifecycle  ┌──────────────┐        │
│  │  Document   │──── stage N ────────│ Stage Runner │        │
│  │  Lifecycle  │◄─── retry/fail ─────│  (retry N)   │        │
│  │  Manager    │                     └──────┬───────┘        │
│  └────────────┘                            │                 │
│       │                           ┌────────┴────────┐       │
│       │                           │  AI Router      │       │
│       ▼                           │  (model per     │       │
│  ┌──────────┐                     │   task)         │       │
│  │ Conf.    │                     └────────┬────────┘       │
│  │ Aggreg.  │                              │                 │
│  └──────────┘                     ┌────────┴────────┐       │
│       │                           │  Human Review   │       │
│       ▼                           │  Orchestrator   │       │
│  ┌──────────┐                     └────────┬────────┘       │
│  │ Commit   │                              │                 │
│  │  TX      │◄─────────────────────────────┘                 │
│  └──────────┘                                               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
PostgreSQL: documents, pipeline_events, domain tables
    │
    ▼
MCP Tools: process_document, get_status, retry, review
```

---

## 1. Document Lifecycle

### State Machine

```
                       ┌─────────┐
                       │ pending │ ← File uploaded, not yet processed
                       └────┬────┘
                            │
                       auto │
                            ▼
                    ┌──────────────┐
                    │ ingesting    │ ← Stage 1: File Ingestion
                    └──────┬───────┘
                     OK    │    FAIL
                    ┌──────┴──────┐
                    ▼             ▼
             ┌──────────┐  ┌────────────┐
             │ ingested │  │ failed_ing │──retry──► ingesting
             └─────┬────┘  └────────────┘
                   │
              auto │
                   ▼
             ┌──────────┐
             │ ocr_pend │ ← Stage 2: OCR
             └─────┬────┘
              OK   │    FAIL
             ┌─────┴──────┐
             ▼            ▼
        ┌─────────┐  ┌─────────┐
        │ ocr_done│  │fail_ocr │──retry──► ocr_pending
        └────┬────┘  └─────────┘
             │
        auto │
             ▼
       ┌───────────┐
       │classify_..│ ← Stage 3: Classification
       └─────┬─────┘
        OK   │     FAIL / LOW CONF
       ┌─────┴──────────┐
       ▼                ▼
  ┌──────────┐   ┌──────────────┐
  │classif'd │   │class_review  │ ← Human review
  └────┬─────┘   └──────┬───────┘
       │           OK   │   REJECT
       │          ┌─────┴──────┐
       │          ▼            ▼
       │    ┌──────────┐  ┌──────────┐
       │    │classif'd │  │ rejected │──► terminal
       │    └────┬─────┘  └──────────┘
       │         │
       │    auto │
       ▼         ▼
  ┌───────────┐
  │extract_.. │ ← Stage 4: Entity Extraction
  └─────┬─────┘
   OK   │     FAIL / LOW CONF
  ┌─────┴──────────┐
  ▼                ▼
┌──────────┐ ┌──────────────┐
│extracted │ │extract_review│ ← Human review
└────┬─────┘ └──────┬───────┘
     │         OK   │   REJECT
     │        ┌─────┴──────┐
     │        ▼            ▼
     │  ┌──────────┐ ┌──────────┐
     │  │extracted │ │ rejected │
     │  └────┬─────┘ └──────────┘
     │       │
     │  auto │
     ▼       ▼
  ┌───────────┐
  │resolve_.. │ ← Stage 5: Entity Resolution
  └─────┬─────┘
   OK   │     NEEDS REVIEW
  ┌─────┴──────────┐
  ▼                ▼
┌──────────┐ ┌──────────────┐
│ resolved │ │resolve_review│ ← Human review
└────┬─────┘ └──────┬───────┘
     │         OK   │   REJECT
     │        ┌─────┴──────┐
     │        ▼            ▼
     │  ┌──────────┐ ┌──────────┐
     │  │ resolved │ │ rejected │
     │  └────┬─────┘ └──────────┘
     │       │
     │  auto │
     ▼       ▼
  ┌──────────┐
  │ staged   │ ← Stages 6+7: Storage + Graph (final, fast)
  └────┬─────┘
   OK  │    FAIL
  ┌────┴──────┐
  ▼           ▼
┌───────┐ ┌────────┐
│ done  │ │failed  │──retry──► staged
└───────┘ └────────┘
```

### State Constants

```python
DOCUMENT_LIFECYCLE = {
    # Initial
    "pending": "File uploaded, not yet processed",

    # Stage 1: Ingestion
    "ingesting": "File validation and conversion in progress",
    "ingested": "File validated, converted, hashed",

    # Stage 2: OCR
    "ocr_pending": "Waiting in OCR queue",
    "ocr_processing": "OCR running",
    "ocr_done": "Text extracted",
    "ocr_failed": "OCR failed (all engines, all pages)",

    # Stage 3: Classification
    "classifying": "Classification in progress",
    "classified": "Document type determined",
    "classify_review": "Classification needs human review",
    "classify_failed": "Classification failed",

    # Stage 4: Extraction
    "extracting": "Entity extraction in progress",
    "extracted": "Entities extracted",
    "extract_review": "Extraction needs human review",
    "extract_failed": "Extraction failed",

    # Stage 5: Resolution
    "resolving": "Entity resolution in progress",
    "resolved": "Entities resolved against existing records",
    "resolve_review": "Resolution needs human review",
    "resolve_failed": "Resolution failed",

    # Stage 6+7: Storage + Graph
    "staging": "Writing domain records + graph edges",
    "staged": "Domain records written, ready for graph",
    "graphing": "Knowledge graph update in progress",

    # Terminal
    "completed": "All stages done. Knowledge available.",
    "rejected": "Human rejected. Document archived.",
    "failed": "Irrecoverable error. Manual intervention required.",
}
```

---

## 2. Stage Execution

### Stage Runner

```python
class StageRunner:
    """Executes a single pipeline stage with retry logic.

    Each stage:
    1. Receives input from previous stage (or file for ingestion)
    2. Updates document status to {stage}_processing
    3. Executes the stage logic
    4. On success: writes result to DB, updates status to {stage}_done
    5. On failure: checks confidence, routes to review or retry
    """

    MAX_RETRIES = {
        "ingestion": 3,
        "ocr": 3,
        "classification": 3,
        "extraction": 2,
        "resolution": 2,
        "storage": 3,
        "graph": 3,
    }

    RETRY_DELAYS = [5, 30, 120]  # seconds between retries

    async def run(
        self,
        stage: str,
        document_id: UUID,
        stage_func: Callable,
        context: StageContext,
    ) -> StageResult:
        """
        Run a stage with retries.

        retry conditions:
          - TransientError (timeout, network, OOM): retry
          - PermanentError (corrupted file, invalid format): no retry
          - Confidence below threshold: route to human review

        Each retry is logged to pipeline_events.
        After MAX_RETRIES exhausted: status = {stage}_failed
        """
        for attempt in range(1, self.MAX_RETRIES.get(stage, 1) + 1):
            try:
                # Update status
                await self._set_status(document_id, f"{stage}_processing")

                # Execute
                result = await stage_func(context)

                # Check confidence
                decision = self._check_confidence(stage, result.confidence)

                if decision == "accept":
                    await self._save_result(document_id, stage, result)
                    await self._set_status(document_id, f"{stage}_done")
                    return StageResult(status="ok", result=result)

                elif decision == "review":
                    await self._save_result(document_id, stage, result)
                    await self._route_to_review(document_id, stage, result)
                    return StageResult(status="needs_review", result=result)

                else:  # reject
                    await self._log_rejection(document_id, stage, result)
                    await self._set_status(document_id, "rejected")
                    return StageResult(status="rejected")

            except TransientError as e:
                await self._log_retry(document_id, stage, attempt, e)
                if attempt < self.MAX_RETRIES.get(stage, 1):
                    await asyncio.sleep(self.RETRY_DELAYS[attempt - 1])
                    continue
                await self._set_status(document_id, f"{stage}_failed")
                return StageResult(status="failed", error=str(e))

            except PermanentError as e:
                await self._log_error(document_id, stage, e)
                await self._set_status(document_id, f"{stage}_failed")
                return StageResult(status="failed", error=str(e))

    def _check_confidence(
        self, stage: str, confidence: float
    ) -> str:
        """
        Map confidence to decision per stage.

        Stages have different thresholds because they
        have different cost/risk profiles.
        """
        thresholds = {
            "classification": {
                "accept": 0.80,
                "review": 0.40,
            },
            "extraction": {
                "accept": 0.85,
                "review": 0.60,
            },
            "resolution": {
                "accept": 0.85,
                "review": 0.50,
            },
        }
        t = thresholds.get(stage, {"accept": 0.85, "review": 0.50})
        if confidence >= t["accept"]:
            return "accept"
        elif confidence >= t["review"]:
            return "review"
        return "reject"
```

### Stage Interface

Every stage follows the same contract:

```python
class StageContext:
    """Context passed through the pipeline.

    Accumulates results from each stage.
    Stages read their input from context, write their output.
    """
    document_id: UUID
    document: Document
    file_path: str
    file_hash: str
    mime_type: str
    page_count: int

    # Set by ingestion
    raw_text: str | None           # native text (DOCX, XLSX)
    image_paths: list[str]         # page images (PDF, JPG, PNG)

    # Set by OCR
    ocr_text: str | None
    ocr_confidence: float
    ocr_layout: dict

    # Set by classification
    document_type: str | None
    classification_confidence: float

    # Set by extraction
    extraction_data: dict          # 7 entity schemas
    extraction_confidence: float

    # Set by resolution
    resolutions: dict              # {entity_id: resolved_uuid}
    resolution_confidence: float

    # Set by storage
    domain_records: dict           # created/updated entity IDs


class StageResult:
    status: str                    # "ok" | "needs_review" | "rejected" | "failed"
    confidence: float
    data: dict                     # stage-specific output
    error: str | None
    suggestions: list[dict] | None # for review: what to show operator
```

---

## 3. AI Router (Per-Task Dispatch)

The runtime routes each stage to the appropriate AI model:

```python
class AIRouter:
    """Maps each pipeline stage + document type to an AI model."""

    ROUTING_TABLE = {
        "ocr": {
            # Document type → (engine, model)
            "default": ("paddleocr", "PP-OCRv4"),
            "fallback": ("tesseract", "5.4"),
            "trigger": "paddle_confidence < 0.6",
        },
        "classification": {
            "stage_1": ("rule", None),           # free, always run
            "stage_2": ("ml", "tfidf-svm"),      # 50ms, needs training
            "stage_3": ("llm", "deepseek-flash"), # 2-5s, last resort
            "fallback_ml": ("skip_to_stage_3",),
        },
        "extract_passport": ("llm", "qwen-local"),
        "extract_receipt": ("llm", "qwen-local"),
        "extract_egrn": ("llm", "deepseek-flash"),
        "extract_power_of_attorney": ("llm", "deepseek-flash"),
        "extract_contract": ("llm", "deepseek-pro"),
        "extract_unknown": ("llm", "deepseek-flash"),
        "resolution_embedding": ("local", "intfloat/multilingual-e5-small"),
        "resolution_llm": ("llm", "deepseek-flash"),
    }

    async def resolve(
        self,
        stage: str,
        document_type: str | None,
        confidence: float | None = None,
    ) -> AIModelRoute:
        """
        Resolve which model to use for this stage.

        For classification with sub-stages (rule → ML → LLM),
        returns the next stage to try based on current confidence.
        For direct stages (ocr, extraction), returns the
        configured model for the document type.
        """
        if stage == "classification" and confidence is not None:
            return self._classification_next_stage(confidence)

        key = f"{stage}_{document_type}" if document_type else stage
        route = self.ROUTING_TABLE.get(
            key,
            self.ROUTING_TABLE.get(stage, {}).get("default",
            ("llm", "deepseek-flash")),
        )
        return AIModelRoute(engine=route[0], model=route[1])
```

---

## 4. Confidence Aggregation

```python
class ConfidenceAggregator:
    """Computes overall document confidence from stage results.

    Aggregation is per-document, used to decide:
    - Can this document be auto-committed?
    - Which entities need human review?

    Formula:
      overall = min(
        classification_confidence * 1.0,
        extraction_confidence * 0.9,     # extraction is harder
        resolution_confidence * 0.95      # resolution can be fuzzy
      )

    Rationale: The weakest stage dominates. Extraction is weighted
    down because it's the most error-prone stage. Resolution is
    weighted down slightly because fuzzy matching is uncertain.
    """

    STAGE_WEIGHTS = {
        "ocr": 1.0,
        "classification": 1.0,
        "extraction": 0.9,     # hardest stage, most errors
        "resolution": 0.95,    # fuzzy matching uncertainty
    }

    THRESHOLDS = {
        "auto_commit": 0.85,    # all entities auto-accepted
        "partial_review": 0.65, # low-confidence entities flagged
        "full_review": 0.40,    # entire document flagged
        "rejected": 0.0,        # not enough confidence, re-upload
    }

    def compute_overall(
        self, stage_confidences: dict[str, float]
    ) -> OverallConfidence:
        """
        stage_confidences: {"ocr": 0.92, "classification": 0.87,
                            "extraction": 0.73, "resolution": 0.80}

        Returns:
          overall: weighted minimum
          per_entity: {entity_type: confidence}
          decision: "auto_commit" | "partial_review" | "full_review" | "rejected"
          low_confidence_entities: [entity_type, ...]  for partial review
        """

        weighted = {
            stage: conf * self.STAGE_WEIGHTS.get(stage, 1.0)
            for stage, conf in stage_confidences.items()
        }
        overall = min(weighted.values())

        if overall >= self.THRESHOLDS["auto_commit"]:
            decision = "auto_commit"
        elif overall >= self.THRESHOLDS["partial_review"]:
            decision = "partial_review"
        elif overall >= self.THRESHOLDS["full_review"]:
            decision = "full_review"
        else:
            decision = "rejected"

        # For partial_review: identify entities below threshold
        low_entities = [
            ent for ent, conf in stage_confidences.items()
            if conf < self.THRESHOLDS["auto_commit"]
        ] if decision == "partial_review" else []

        return OverallConfidence(
            overall=round(overall, 3),
            decision=decision,
            low_confidence_entities=low_entities,
        )
```

### Confidence Decision Matrix

| Overall | Decision | What Happens | Human Involved? |
|---------|----------|-------------|-----------------|
| ≥ 0.85 | auto_commit | All entities written to DB. Graph updated. | No |
| 0.65–0.84 | partial_review | High-confidence entities committed. Low-confidence entities flagged with Telegram inline buttons. Operator confirms/rejects per entity. | Yes — per entity |
| 0.40–0.64 | full_review | No entities committed. Full document sent to operator for manual extraction and correction. | Yes — full document |
| < 0.40 | rejected | Document closed as rejected. Telegram notification: "Пожалуйста, загрузите документ в лучшем качестве." | Notification only |

---

## 5. Human Review Orchestration

```python
class ReviewOrchestrator:
    """Manages the pause/resume cycle for human review.

    When a stage routes to review:
    1. Pipeline pauses (document status = {stage}_review)
    2. Review task created in resolution_reviews
    3. Telegram notification sent to assigned agent
    4. MCP tool exposes pending reviews
    5. Agent responds via Telegram inline buttons or MCP
    6. Pipeline resumes from the paused stage
    """

    async def request_review(
        self,
        document_id: UUID,
        stage: str,
        context: StageContext,
        result: StageResult,
    ) -> ReviewTicket:
        """Create a review ticket and notify the agent."""

        ticket = ReviewTicket(
            document_id=document_id,
            stage=stage,
            status="pending",
            data=result.data,
            suggestions=result.suggestions,
            confidence=result.confidence,
        )
        # store in resolution_reviews
        await self._save_ticket(ticket)

        # notify via Telegram
        await self.telegram_notifier.notify_review(
            ticket=ticket,
            assigned_to=context.document.assigned_to,
        )

        return ticket

    async def resolve_review(
        self,
        ticket_id: UUID,
        decision: str,          # "accept" | "edit" | "reject"
        corrections: dict | None = None,
    ) -> PipelineResumeCommand:
        """
        Process agent's review response.

        accept:  resume pipeline with current data
        edit:    apply corrections, resume with modified data
        reject:  set document status to 'rejected', stop pipeline

        Returns a PipelineResumeCommand that the runtime
        uses to continue execution.
        """
        ticket = await self._get_ticket(ticket_id)
        ticket.status = "resolved"

        if decision == "reject":
            await self._set_document_status(
                ticket.document_id, "rejected"
            )
            return PipelineResumeCommand(action="stop")

        if decision == "edit" and corrections:
            # Apply corrections to stage context
            ticket.data = self._apply_corrections(
                ticket.data, corrections
            )

        # Resume pipeline from where it paused
        return PipelineResumeCommand(
            action="resume",
            stage=ticket.stage,
            document_id=ticket.document_id,
            modified_data=ticket.data,
        )
```

### Telegram Review Message

```
📄 *Требуется проверка*
───────────────
Файл: договор_купли_продажи.pdf
Статус: Классификация (точность: 72%)

⚠️ *Тип документа не определён уверенно*
Варианты:
1. sale_contract (72%)
2. rental_contract (18%)
3. unknown (10%)

[✅ sale_contract] [🏠 rental_contract] [❌ Отклонить]
```

---

## 6. Commit Transaction

### Atomic Commit

The final stage bundles all resolved entities into a single database transaction:

```python
class CommitTransaction:
    """Atomic commit of all extracted knowledge.

    This is the ONLY place where domain tables are written
    from the pipeline. Everything before is staging data
    (ocr_results, document_classifications, extracted_entities).

    The commit is wrapped in a single PostgreSQL transaction.
    If any part fails, NOTHING is written to domain tables.
    """

    async def commit(
        self,
        document_id: UUID,
        context: StageContext,
    ) -> CommitResult:
        """
        Atomic transaction:

        1. Create or update domain entities (clients, properties, deals)
        2. Create entity↔document links
        3. Update or create graph nodes + edges
        4. Compute and store embeddings
        5. Update document status to 'completed'
        6. Log pipeline_events
        """

        async with async_session_factory() as session:
            async with session.begin():
                # 1. Domain entities
                created_entities = {}
                for entity_type, entities in self._get_entities(context):
                    for entity in entities:
                        resolved_id = context.resolutions.get(entity.id)
                        if resolved_id:
                            # Enrich existing
                            await self._enrich_entity(
                                session, entity_type, resolved_id, entity
                            )
                            created_entities[entity.id] = resolved_id
                        else:
                            # Create new
                            new_id = await self._create_entity(
                                session, entity_type, entity
                            )
                            created_entities[entity.id] = new_id

                # 2. Document → entity links
                for extracted_id, resolved_id in created_entities.items():
                    await self._link_document_to_entity(
                        session, document_id, resolved_id,
                    )

                # 3. Graph nodes + edges
                for entity_type, entity_id in created_entities.items():
                    await self._ensure_graph_node(
                        session, entity_type, entity_id
                    )
                await self._create_document_graph_edges(
                    session, document_id, created_entities
                )

                # 4. Embeddings (async, non-blocking)
                asyncio.create_task(
                    self._compute_embeddings(created_entities)
                )

                # 5. Finalize
                doc = await session.get(Document, document_id)
                doc.status = "completed"

                # 6. Audit event
                await self._log_pipeline_event(
                    session, document_id, "completed",
                    metadata={"entities_created": len(created_entities)},
                )

            return CommitResult(
                status="committed",
                entity_count=len(created_entities),
                document_id=document_id,
            )
```

### Rollback Strategy

```python
ROLLBACK_STRATEGY = {
    "scope": "per_document",
    "mechanism": {
        "before_commit": {
            "method": "DELETE staging rows",
            "sql": """
                DELETE FROM ocr_results WHERE document_id = :doc_id;
                DELETE FROM document_classifications WHERE document_id = :doc_id;
                DELETE FROM extracted_entities WHERE document_id = :doc_id;
                DELETE FROM entity_resolutions
                    WHERE extracted_entity_id IN (
                        SELECT id FROM extracted_entities
                        WHERE document_id = :doc_id
                    );
                UPDATE documents SET status = 'pending',
                    processing_attempts = processing_attempts + 1
                WHERE id = :doc_id;
            """,
            "safe": True,  # staging data only
        },
        "after_commit": {
            "method": "soft-delete domain records",
            "sql": """
                UPDATE documents SET status = 'rollback' WHERE id = :doc_id;
                UPDATE clients SET deleted_at = NOW()
                    WHERE id IN (
                        SELECT entity_id FROM pipeline_events
                        WHERE document_id = :doc_id
                          AND event = 'entity_created'
                    );
                -- Similar for properties, deals
                DELETE FROM graph_edges WHERE source IN (
                    SELECT id FROM graph_nodes
                    WHERE entity_id IN (
                        SELECT entity_id FROM pipeline_events
                        WHERE document_id = :doc_id
                          AND event = 'entity_created'
                    )
                );
            """,
            "safe": False,  # data loss risk, requires operator confirmation
        },
    },
    "triggers": {
        "auto_rollback": [
            "stage_timeout > MAX_RETRIES exhausted",
            "critical_validation_error",
            "database_connection_lost",
        ],
        "manual_rollback": [
            "operator detects incorrect extraction",
            "test document processed in production",
        ],
    },
}
```

---

## 7. Pipeline Audit Trail

### pipeline_events Table

```sql
CREATE TABLE pipeline_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Event classification
    event_type VARCHAR(30) NOT NULL,
    -- stage_started | stage_completed | stage_failed |
    -- stage_retry | review_requested | review_resolved |
    -- committed | rollback | rejected

    -- Stage context
    stage VARCHAR(20) NOT NULL,          -- ingestion|ocr|classification|...
    stage_attempt INTEGER DEFAULT 1,

    -- Timing
    duration_ms INTEGER,                 -- how long this stage took
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,

    -- Result
    status VARCHAR(20) NOT NULL,          -- ok | failed | needs_review | retry
    confidence FLOAT,
    error_message TEXT,
    error_type VARCHAR(50),              -- TransientError | PermanentError | ...

    -- Metadata
    model_used VARCHAR(100),              -- which AI model was invoked
    input_size_bytes INTEGER,            -- document size
    metadata JSONB DEFAULT '{}',          -- stage-specific debug info

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_events_doc ON pipeline_events(document_id);
CREATE INDEX idx_pipeline_events_type ON pipeline_events(event_type);
CREATE INDEX idx_pipeline_events_stage ON pipeline_events(stage);
CREATE INDEX idx_pipeline_events_created ON pipeline_events(created_at DESC);
```

### Event Flow Example

```
document_id: abc-123

event_type        | stage         | status    | duration_ms | confidence
──────────────────┼───────────────┼───────────┼─────────────┼───────────
stage_started     | ingestion     | running   | 0           | NULL
stage_completed   | ingestion     | ok        | 320         | NULL
stage_started     | ocr           | running   | 0           | NULL
stage_retry       | ocr           | retry     | 15200       | 0.45
stage_completed   | ocr           | ok        | 18900       | 0.91
stage_started     | classification| running   | 0           | NULL
stage_completed   | classification| ok        | 2340        | 0.87
stage_started     | extraction    | running   | 0           | NULL
stage_completed   | extraction    | ok        | 8450        | 0.73
stage_started     | resolution    | running   | 0           | NULL
review_requested  | resolution    | needs_rev | 120         | 0.62
review_resolved   | resolution    | ok        | 3420000     | 0.95 ← 57 min later
stage_started     | storage       | running   | 0           | NULL
stage_completed   | storage       | ok        | 210         | NULL
committed         | commit        | ok        | 450         | 0.95
```

---

## 8. Pipeline Orchestrator (Runtime)

```python
class KnowledgeRuntime:
    """Top-level runtime that runs the full pipeline.

    One instance per document. Stateless — all state
    is in the database (documents.status + pipeline_events).
    """

    STAGES = [
        ("ingestion", FileIngestionService),
        ("ocr", OCRService),
        ("classification", ClassificationService),
        ("extraction", ExtractionService),
        ("resolution", ResolutionService),
        ("storage", CommitTransaction),
        ("graph", GraphBuilder),
    ]

    async def process(
        self,
        file_path: str,
        user_id: UUID,
        metadata: dict | None = None,
    ) -> PipelineResult:
        """
        Process one document through the full pipeline.

        This is the main entry point called by:
          - POST /api/v1/documents/process
          - MCP tool: process_document
          - Telegram file upload handler
        """

        # Create document record
        doc = await self.document_store.create(
            file_path=file_path,
            uploaded_by=user_id,
            metadata=metadata or {},
            status="pending",
        )

        context = StageContext(document_id=doc.id)

        # Run stages
        for stage_name, service_cls in self.STAGES:
            runner = StageRunner()
            service = service_cls()

            result = await runner.run(
                stage=stage_name,
                document_id=doc.id,
                stage_func=service.execute,
                context=context,
            )

            if result.status == "needs_review":
                # Pause pipeline, wait for human
                return PipelineResult(
                    status="paused_for_review",
                    document_id=doc.id,
                    stage=stage_name,
                )

            elif result.status == "failed":
                return PipelineResult(
                    status="failed",
                    document_id=doc.id,
                    stage=stage_name,
                    error=result.error,
                )

            elif result.status == "rejected":
                return PipelineResult(
                    status="rejected",
                    document_id=doc.id,
                    stage=stage_name,
                )

        return PipelineResult(
            status="completed",
            document_id=doc.id,
        )

    async def resume_from_review(
        self,
        document_id: UUID,
        stage: str,
        modified_data: dict | None = None,
    ) -> PipelineResult:
        """
        Resume pipeline after human review.

        Called by:
          - MCP tool: resolve_review
          - Telegram callback: review_resolve
        """
        context = await self._rebuild_context(document_id)
        if modified_data:
            context = self._apply_modifications(context, modified_data)

        # Resume from the stage that was paused
        start_index = next(
            i for i, (name, _) in enumerate(self.STAGES)
            if name == stage
        )

        for stage_name, service_cls in self.STAGES[start_index:]:
            # ... same loop as process()
            pass
```

---

## 9. Retry Strategy (Summary)

| Stage | Max Retries | Retry On | No Retry On | Delay |
|-------|-------------|----------|-------------|-------|
| ingestion | 3 | Timeout, disk full | Corrupted file, password-protected PDF | 5s, 30s, 120s |
| ocr | 3 | OOM, Paddle crash, GPU OOM | All pages empty, format unsupported | 5s, 30s, 120s |
| classification | 3 | LLM timeout, ML model not loaded | Empty text input | 5s, 15s, 45s |
| extraction | 2 | LLM timeout, invalid JSON response | Empty document (no text) | 3s, 9s |
| resolution | 2 | DB connection lost, embedding model timeout | Entity has no identifying fields | 3s, 9s |
| storage | 3 | Deadlock, serialization error, connection pool empty | FK violation (should not happen) | 1s, 5s, 15s |
| graph | 3 | Deadlock, constraint violation | — | 1s, 5s, 15s |

### Backoff Profile

```
attempt 1 → wait 5s → attempt 2 → wait 30s → attempt 3 → wait 120s → fail
```

All retries are logged to `pipeline_events` with `event_type = 'stage_retry'` and the error message preserved in `error_message`.

---

## 10. MCP Integration

### MCP Tools Exposed by the Runtime

```python
MCP_TOOLS = {
    "process_document": {
        "description": "Upload and process a document",
        "params": {"file_path": "str", "user_id": "UUID"},
        "returns": {"document_id": "UUID", "status": "str"},
    },
    "get_document_status": {
        "description": "Get processing status and confidence",
        "params": {"document_id": "UUID"},
        "returns": {"status": "str", "confidence": "float",
                    "current_stage": "str", "pipeline_events": "list"},
    },
    "get_pending_reviews": {
        "description": "List documents waiting for human review",
        "params": {"assigned_to": "UUID | None", "limit": "int"},
        "returns": [{"review_id", "document_id", "stage", "confidence"}],
    },
    "resolve_review": {
        "description": "Submit review decision and resume pipeline",
        "params": {"review_id": "UUID",
                   "decision": "accept | edit | reject",
                   "corrections": "dict | None"},
        "returns": {"status": "resolved", "document_status": "str"},
    },
    "retry_document": {
        "description": "Retry a failed document from a specific stage",
        "params": {"document_id": "UUID", "from_stage": "str"},
        "returns": {"status": "processing", "document_id": "UUID"},
    },
    "rollback_document": {
        "description": "Rollback a completed document (operator only)",
        "params": {"document_id": "UUID", "reason": "str"},
        "returns": {"status": "rollback_initiated"},
    },
    "get_pipeline_events": {
        "description": "Get full audit trail for a document",
        "params": {"document_id": "UUID"},
        "returns": {
            "events": [{"event_type", "stage", "duration_ms", "status"}]
        },
    },
}
```

---

## 11. Performance Targets

| Metric | Target | Condition |
|--------|--------|-----------|
| Single page OCR (CPU) | < 5 sec | PaddleOCR, 300 DPI |
| Full pipeline (passport) | < 20 sec | 1 page, Qwen extraction |
| Full pipeline (contract) | < 60 sec | 10 pages, DeepSeek Pro |
| Human review notification | < 5 sec | Telegram delivery |
| Review → resume latency | < 2 sec | After agent clicks accept |
| Batch throughput | 100 docs/hour | Single CPU worker |
| Pipeline event write | < 10 ms | Append-only, no contention |

---

## 12. Error Taxonomy (Stage-Specific)

```python
# Transient — retry automatically
class TransientError(PipelineError):
    """Network timeout, model OOM, DB deadlock."""

class StageTimeout(TransientError):
    """Stage exceeded its time budget."""

class ModelOOM(TransientError):
    """AI model ran out of memory (GPU/CPU)."""

class DBDeadlock(TransientError):
    """PostgreSQL deadlock detected."""

# Permanent — do not retry
class PermanentError(PipelineError):
    """Corrupted file, invalid format, empty input."""

class CorruptedFileError(PermanentError):
    """File cannot be read (truncated, header mismatch)."""

class InvalidFormatError(PermanentError):
    """MIME type not in supported list."""

class EmptyInputError(PermanentError):
    """OCR produced zero text (blank pages)."""

class ValidationRejection(PipelineError):
    """Stage result failed validation — route to human review."""
```

---

## Related Documentation

- `docs/architecture/knowledge_agent_v1.md` — Agent orchestrator architecture
- `docs/architecture/ocr_layer.md` — OCR engine details
- `docs/architecture/document_classifier.md` — 3-stage classification
- `docs/architecture/entity_extraction.md` — 7 entity extraction schemas
- `docs/architecture/entity_resolution.md` — 4-stage resolution pipeline
- `docs/architecture/knowledge_graph.md` — Graph adjacency model
- `docs/architecture/backend_bootstrap.md` — Backend service layer patterns
- `docs/adr/0011-knowledge-agent-v1.md` — Agent ADR
