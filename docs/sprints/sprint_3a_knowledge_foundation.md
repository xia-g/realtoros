# Sprint 3A: Knowledge Foundation Platform — Report

**Date:** 2026-06-08
**Status:** Completed
**Verification:** 19/19 checks pass

---

## Architecture Overview

```
Document (PDF/JPG/PNG/TIFF)
    |
    v
OCRService (PaddleOCR -> Tesseract fallback)
    |
    v
DocumentClassifier (rules -> embeddings -> LLM cascade)
    |
    v
EntityExtractionService (patterns -> DeepSeek LLM)
    |
    v
EntityResolutionService (exact -> fuzzy -> embedding)
    |
    v
KnowledgeGraphBuilder (nodes + edges, idempotent upsert)
    |
    v
EmbeddingPipeline (multilingual-e5-small, 384-dim)
    |
    v
KnowledgeSearchService (hybrid BM25 + vector cosine)
```

## Storage Layer (Phase 1)

### 4 new tables (Migration 005)

| Table | Purpose | Key Indexes |
|-------|---------|-------------|
| `embeddings` | Vector storage (384-dim), HNSW + IVFFlat | entity lookup, content_hash unique |
| `document_chunks` | Split document text with token count | document_id, doc+chunk unique |
| `graph_nodes` | Entity nodes (client, property, deal, etc.) | node_type, entity_id unique |
| `graph_edges` | Relationship edges (owns, refers_to, etc.) | source, target, edge_type |

### pgvector enabled
```sql
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(384);
CREATE INDEX ix_embeddings_hnsw ON embeddings USING hnsw (embedding vector_cosine_ops);
```

## AI Domain (Phases 2-8)

### OCR Runtime

| Component | Detail |
|-----------|--------|
| Primary engine | PaddleOCR PP-OCRv4 (ru lang, angle cls) |
| Fallback | Tesseract 5 (rus+eng) |
| PDF support | PyMuPDF -> per-page image -> PaddleOCR |
| Output | OCRResult(text, confidence, page_count, provider) |
| Audit | ocr_started, ocr_completed, ocr_failed |

### Document Classifier

| Strategy | Order | Threshold |
|----------|-------|-----------|
| Rules (keyword matching) | 1st | >= 0.85 auto accept |
| Embeddings (e5-small) | 2nd | Sprint 7 |
| LLM (DeepSeek) | 3rd | Sprint 4 |

9 supported classes: passport, egrn, contract, power_of_attorney, receipt, bank_document, tax_document, communication, commercial_offer, unknown.

### Entity Extraction

| Entity | Extraction Method | Fields |
|--------|------------------|--------|
| Person | Pattern regex + LLM | full_name, phone, email |
| Property | Pattern regex | cadastral_number, address |
| Deal | LLM (stub until S4) | amount, commission |
| Document | LLM (stub until S4) | issue_date, registration_number |
| Organization | Pattern regex | name, inn, ogrn |

### Entity Resolution

| Strategy | Threshold | Action |
|----------|-----------|--------|
| Exact (phone/email/cadastral) | 0.99 | auto-link |
| Fuzzy (name similarity) | >= 0.95 | auto-link |
| Fuzzy | 0.75 - 0.94 | review queue |
| No match | < 0.75 | create candidate |

### Knowledge Graph

| Aspect | Detail |
|--------|--------|
| Node types | client, property, deal, document, lead, communication, organization |
| Edge types | owns, participates_in, related_to, generated_from, refers_to, converts_to |
| Idempotency | upsert by (node_type, entity_id) — no duplicates |
| Full rebuild | delete all + re-insert |

### Embedding Pipeline

| Aspect | Detail |
|--------|--------|
| Model | intfloat/multilingual-e5-small |
| Dimension | 384 |
| Storage | embeddings table with HNSW + IVFFlat indexes |
| Dedup | content_hash (SHA256) |
| Batching | Per-document chunk embedding |

### Semantic Search

| Method | Detail |
|--------|--------|
| Full-text | PostgreSQL ts_rank (russian) on document_chunks |
| Vector | cosine_distance on embeddings |
| Hybrid | 30% BM25 + 70% vector = final score |
| Entities | document, client, property, deal, lead |

## API Endpoints (Phase 9)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/knowledge/search | Semantic search across all entities |
| GET | /api/v1/knowledge/document/{id} | Get document knowledge |
| GET | /api/v1/knowledge/graph/entity/{id} | Entity graph (node + edges) |
| POST | /api/v1/knowledge/rebuild | Full graph rebuild |
| GET | /api/v1/knowledge/stats | Knowledge storage statistics |

## Scheduler Integration (Phase 10)

| Job | Trigger | Description |
|-----|---------|-------------|
| knowledge_sync_daily | daily | Process pending documents |
| graph_rebuild_daily | daily | Full graph rebuild |
| embedding_rebuild_weekly | weekly | Regenerate all embeddings |
| document_retry_hourly | hourly | Retry failed documents |
| orphan_cleanup_daily | daily | Remove dangling nodes |

Registered via `register_task()` using existing System Jobs infrastructure.

## Observability (Phase 11)

| Metric | Type | Description |
|--------|------|-------------|
| knowledge_documents_total | Counter | Documents processed (status, doc_type) |
| knowledge_ocr_duration_seconds | Histogram | OCR duration (provider) |
| knowledge_classification_duration_seconds | Histogram | Classification duration (strategy) |
| knowledge_extraction_duration_seconds | Histogram | Extraction duration (doc_type) |
| knowledge_resolution_duration_seconds | Histogram | Resolution duration (entity_type) |
| knowledge_graph_nodes_total | Gauge | Total graph nodes |
| knowledge_graph_edges_total | Gauge | Total graph edges |
| knowledge_embedding_duration_seconds | Histogram | Embedding generation |
| knowledge_search_latency_seconds | Histogram | Search latency (entity_type) |

## Files Created (25 files)

```
backend/
  ai/
    __init__.py
    metrics.py
    ocr/__init__.py
    classifier/__init__.py
    extraction/__init__.py
    resolution/__init__.py
    graph/__init__.py
    embeddings/__init__.py
    search/__init__.py
    pipeline/__init__.py          (scheduler jobs)
    pipeline/orchestrator.py      (end-to-end pipeline)
  models/
    document_chunk.py
    embedding.py
    graph_node.py
    graph_edge.py
  migrations/versions/
    005_add_knowledge_foundation.py
  api/routes/
    knowledge.py
```

## Files Modified (5 files)

| File | Change |
|------|--------|
| backend/models/__init__.py | Added 4 new models |
| backend/api/router.py | Added /api/v1/knowledge routes |
| backend/repositories/__init__.py | Added NotificationRepository (previous sprint) |
| backend/requirements.txt | Added pgvector, paddleocr, sentence-transformers |
| backend/database.py | Clean (Base stays pure, pgvector registered via migration) |

## Acceptance Criteria

- [x] 4 new tables (embeddings, document_chunks, graph_nodes, graph_edges)
- [x] pgvector extension + HNSW/IVFFlat indexes
- [x] OCR Runtime (PaddleOCR primary, Tesseract fallback)
- [x] Document Classifier (rules-based, 9 classes, >= 0.85 auto-accept)
- [x] Entity Extraction (patterns + LLM stub)
- [x] Entity Resolution (exact -> fuzzy -> embedding, 3 thresholds)
- [x] Knowledge Graph Builder (6 node types, 6 edge types, idempotent)
- [x] Embedding Pipeline (e5-small, 384-dim, dedup by hash)
- [x] Semantic Search (hybrid BM25 + vector, top 20 results)
- [x] 5 API endpoints (search, document, graph, rebuild, stats)
- [x] 5 scheduled jobs (daily hourly weekly)
- [x] 9 Prometheus metrics
- [x] Pipeline Orchestrator (7-step end-to-end processing)

## Ready for Sprint 4 (AI Runtime)

Knowledge Foundation Platform provides the storage, processing, and search infrastructure needed for:

- **Sprint 4:** Live LLM integration for extraction + classification
- **Sprint 5:** Knowledge Agent with memory and reasoning
- **Sprint 6:** Lead scoring via vector similarity
- **Sprint 7:** Business Assistant with semantic search
