# RealtorOS v2.1.1 — Projection Architecture

> **Bridge between Domain v2.0 and Knowledge Query.**
> Tag: `v2.1.1-projections.complete`

---

## 1. Purpose

The Projection Layer materialises immutable Domain objects into immutable
Read Models suitable for consumption by the Query Engine.

Domain v2.0 defines *what* the platform knows. The Projection Layer defines
*how* that knowledge is organised for access. It is the first architectural
layer above Domain and the last purely abstract layer — no database, no
storage implementation, no infrastructure.

**It is not responsible for:**
- executing queries (delegated to v2.1.3 Query Engine);
- accepting predicates or filters (delegated to v2.1.2 Query DSL);
- optimising access plans (delegated to v2.1.3 Engine);
- persisting data (delegated to v2.1.4 Infrastructure).

---

## 2. Public API

```
projection/
├── projection.py              # Projection (Protocol), ProjectionId, ProjectionType
├── projection_digest.py       # ProjectionDigest, ProjectionDigestResult
├── build_plan.py              # BuildPlan, BuildStep
├── projection_builder.py      # ProjectionBuilder (Protocol)
├── projection_registry.py     # ProjectionRegistry
├── projection_coordinator.py  # ProjectionCoordinator, CoordinatorResult
├── projection_store.py        # ProjectionStore (Protocol)
├── projection_query_service.py# ProjectionQueryService
├── staleness.py               # StalenessService, StalenessResult, StalenessState
└── exceptions.py              # ProjectionError hierarchy
```

### Key types

| Symbol | Kind | Description |
|--------|------|-------------|
| `Projection` | Protocol | Base for all Read Models |
| `ProjectionId` | Value Object | Immutable projection identifier |
| `ProjectionType` | Enum | ENTITY, OWNERSHIP, TIMELINE, GRAPH, RISK, AGREEMENT, PROVENANCE |
| `ProjectionDigest` | Value Object | Deterministic digest from KnowledgeRevision |
| `BuildPlan` | Model | Declarative plan — no bool flags |
| `BuildStep` | Value Object | Single plan step with optional dependencies |
| `ProjectionBuilder` | Protocol | Domain → Projection transformation |
| `ProjectionRegistry` | Service | Maps `ProjectionType → ProjectionBuilder` |
| `ProjectionCoordinator` | Service | Orchestrator — receives BuildPlan, delegates to Builders, stores results |
| `CoordinatorResult` | Value Object | Built / skipped / errors |
| `ProjectionStore` | Protocol | `put/get/remove/contains/get_digest` |
| `ProjectionQueryService` | Service | Read-only: `get/exists/get_many/get_digest` |
| `StalenessService` | Service | Fresh / Stale / Missing via Digest only |

---

## 3. Dependency Rules

```
v2.1.4 Infrastructure (Store impl., Adapters)
    ↑
v2.1.3 Query Engine (Planner, Optimizer)
    ↑
v2.1.2 Knowledge Query DSL (Intent Document, Predicates)
    ↑
────────────────────────────────────────
v2.1.1 Projection Layer
────────────────────────────────────────
    ↑
v2.0 Domain (Frozen)
```

**Inside the Projection Layer:**

```
Coordinator  ───→  Registry  ───→  Builder  ───→  Domain
    │
    └──→  Store (Protocol)
    │
    └──→  QueryService (via Store)
    │
    └──→  StalenessService (via Store)
```

- **Builder** is the only component that reads Domain
- **Store** depends on nothing (Protocol only)
- **Projection** depends on nothing
- **Coordinator** orchestrates via Registry + Store Protocol
- **Registry** maps types, knows Builders but not Store
- **QueryService** and **StalenessService** depend only on Store

---

## 4. Architectural Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Immutable** | All Projections, Plans, Digests are `@dataclass(frozen=True)` |
| 2 | **Deterministic** | Same Domain input → bit-identical Projection |
| 3 | **Persistence Agnostic** | Store is a Protocol — no SQL, Neo4j, Elastic |
| 4 | **Infrastructure Free** | No I/O, no files, no network calls |
| 5 | **Builder Isolation** | Only Builder has access to Domain |
| 6 | **Read Model Only** | Projections contain no business logic |
| 7 | **Explicit Dependencies** | All dependencies via Protocols |
| 8 | **No Query Logic** | No predicates, filters, joins, sorts, aggregations |
| 9 | **Single Responsibility** | Each component has exactly one concern |
| 10 | **No Business Logic** | Builders transform; they do not decide |
| 11 | **KnowledgeQuery is intent, not execution** | KnowledgeQuery describes *what* to find, never *how* to execute. It has zero knowledge of Store, Planner, Optimizer, Index, or Projection internals. |

### 4.1. The KnowledgeQuery Invariant

This principle is the foundation of the entire Query DSL (v2.1.2):

> **KnowledgeQuery is a description of intent, not an execution instruction.**

From it follows that KnowledgeQuery:

- **does not know** about `ProjectionStore`;
- **does not know** about `Planner`;
- **does not know** about `ExecutionPlan`;
- **does not know** about `Optimizer`;
- **does not know** about `Index`;
- **does not know** about specific `Projection` types;
- **does not know** about infrastructure or storage details.

It expresses **only** *what* to retrieve — the subject, predicates, relationships —
and leaves *how* to retrieve it entirely to the layers below (Engine, Planner, Store).

This boundary is as strict as the Domain → Projection boundary.
A KnowledgeQuery that references a `ProjectionStore` or an `ExecutionPlan`
is architecturally invalid.

---

## 5. Out of Scope

The following are intentionally **excluded** from Projection Layer
and belong to subsequent layers (v2.1.2–v2.1.4):

- **Knowledge Query DSL** — predicates, filters, `WHERE`, `JOIN`, `ORDER BY`, `LIMIT`
- **Execution Plan** — Planner, Optimizer, Strategy
- **Index Selection** — no indexes in this layer
- **SQL / Neo4j / Elastic** — any database technology
- **Caching** — belongs to Infrastructure
- **Repository** — is a Domain concept; Projections use Store, not Repository
- **Materialized View** — Projection is a logical concept, not a DB view
- **Transactions** — no transactional boundaries
- **Eventual Consistency** — not a concern of this layer
- **Search** — no full-text or semantic search

---

## 6. Projection Lifecycle

```
KnowledgeRevision (from Domain v2.0)
    │
    ▼
ProjectionDigest.from_revision(revision)
    │
    ▼
StalenessService.check(projection_id, digest)
    │
    ├── FRESH  → return existing Projection (no rebuild)
    ├── STALE  → rebuild via Coordinator
    └── MISSING → build via Coordinator
                     │
                     ▼
BuildPlan → Coordinator
    │
    ▼
Registry.get(type) → Builder.build(domain_state) → Projection
    │
    ▼
Store.put(projection) + Store.put_digest(digest)
    │
    ▼
QueryService.get(projection_id)
```

---

> **Tag:** `v2.1.1-projections.complete`
>
> **Domain v2.0 frozen.** Projection Layer open for v2.1.2–v2.1.4.
>
> Tests: 40 projection + 756 project-wide = **796 total** ✅
