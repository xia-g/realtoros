# Real Estate OS

AI-платформа для агентства недвижимости. Knowledge-driven pipeline.

## Tech Stack

| Компонент | Технология |
|-----------|-----------|
| Backend | Python 3.13 / FastAPI |
| Frontend | Next.js |
| Database | PostgreSQL 17 |
| OCR | Tesseract 5 (CPU) |
| Vector Search | intfloat/multilingual-e5-small |
| LLM | Qwen2.5-32B (llama.cpp, CPU) |
| ML Pipeline | Domain-driven Knowledge Graph |

## Architecture

### Knowledge Runtime (v2.3.1)

```
┌────────────────────────────────────────────────────────────────────┐
│                        FastAPI (:8090)                              │
│                                                                     │
│  ┌─ lifespan ─────────────────────────────────────────────────┐     │
│  │  Settings.DATABASE_SYNC_URL  →  Repositories  →  Integrator │     │
│  │             app.state.integrator — доступен всем роутам      │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ┌─ Composition Root ──────────────────────────────────────────┐   │
│  │  PostgreSQLKnowledgeRevisionRepository                       │   │
│  │  PostgreSQLProjectionStore                                   │   │
│  │  KnowledgeRuntimeIntegrator(revision_repository,              │   │
│  │                              projection_store)               │   │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ┌─ Domain Pipeline (per request) ─────────────────────────────┐   │
│  │  OCR → Semantic → DomainPipelineBridge → RevisionBuilder     │   │
│  │  RevisionSnapshotFactory → KnowledgeRevision (snapshot)      │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ Persistence ───────────────────────────────────────────────┐  │
│  │  knowledge_revisions (JSONB: graph, provenance, explanation) │   │
│  │  projection_store     (JSONB: ENTITY/AGREEMENT/GRAPH/       │   │
│  │                                PROVENANCE + digests)        │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ Query ─────────────────────────────────────────────────────┐  │
│  │  KnowledgeQuery → KnowledgeQueryEngine → ExecutionPlan       │   │
│  │  → ProjectionQueryService → ProjectionStore → QueryResult    │   │
│  └────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

### Application Lifecycle

#### Startup

```
uvicorn (gunicorn)
    │
FastAPI lifespan()
    ├── DatabaseHealthCheck.check()  ← ping PostgreSQL
    ├── register_sync_handlers()     ← event bus
    │
    ├── PostgreSQLKnowledgeRevisionRepository(dsn=settings.DATABASE_SYNC_URL)
    ├── PostgreSQLProjectionStore(dsn=settings.DATABASE_SYNC_URL)
    │
    └── KnowledgeRuntimeIntegrator(
            revision_repository=...,
            projection_store=...,
        )
            ↓
    app.state.integrator = integrator
            ↓
    Runtime Ready ← QueryEngine доступен без единого документа
```

#### Document Processing

```
upload(request)
    │
    ├── OCR Node (GPU) / Tesseract fallback (CPU)
    ├── Semantic Reclassification
    ├── Deal Resolution
    │
    └── DomainPipelineBridge.process()
            │
            ├── Business Facts
            ├── Agreement Resolution
            ├── Canonical Identity
            ├── Knowledge Evolution
            ├── Knowledge Graph
            ├── Explainability (GraphExplanation)
            ├── Provenance (KnowledgeProvenance)
            └── RevisionBuilder.build()
                    = KnowledgeRevision(snapshot=KnowledgeSnapshot)
                    │
                    ↓
            KnowledgeRuntimeIntegrator.integrate()
                    │
                    ├── Step 1: Save record → PostgreSQLKnowledgeRevisionRepository
                    ├── Step 2: Materialize → ENTITY, AGREEMENT, GRAPH, PROVENANCE
                    ├── Step 3: Store → PostgreSQLProjectionStore
                    ├── Step 4: Query diagnostics
                    └── Step 5: Structured log
                            │
                            ↓
                    Runtime Report (revision_id, projections, queries)
```

### Dependencies (unidirectional)

```
infrastructure                    ← psycopg2, JSONB, Settings
    ↑
application                       ← Integrator, Materialization, Repository
    ↑
domain                            ← KnowledgeRevision, Graph, Provenance, Explanation
    ↑
projection / query / query_engine ← ProjectionStore, KnowledgeQuery, ExecutionPlan
    ↑
infrastructure (composition_root) ← конфигурация адаптеров
```

All layers import only layers **below** them. Domain imports nothing.

### Tags

| Tag | Что |
|-----|-----|
| `v2.2.0-runtime-snapshot` | DomainPipelineBridge fix |
| `v2.3.0-persistence` | PostgreSQL Repository + ProjectionStore |
| `v2.3.1-runtime-bootstrap` | Recovery / Bootstrap, DI, lifespan |

## Quick Start

```bash
cd /home/xiag/real-estate-os
source venv/bin/activate

# Backend
uvicorn backend.main:app --host 0.0.0.0 --port 8090

# Frontend
cd frontend && npx next dev -p 3000
```

## Tests

```bash
# All accounting_binding tests
PYTHONPATH=services/accounting_binding:$PYTHONPATH \
  python3 -m pytest services/accounting_binding/tests/ \
  --ignore=services/accounting_binding/tests/chaos -q

# PostgreSQL integration tests (require running PG)
PYTHONPATH=services/accounting_binding:$PYTHONPATH \
  python3 -m pytest services/accounting_binding/tests/infrastructure/ -q
```

Current: 964 tests passing.
