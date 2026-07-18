# RealtorOS v2.1.3 — Query Engine Architecture

> **Execution bridge between declarative Query DSL and concrete data access.**
> Tag: `v2.1.3-query-engine.done`

---

## 1. Purpose

The Knowledge Query Engine is the first architectural layer in RealtorOS that
introduces **behaviour** — planning, execution, and result assembly.

Before it:

- **Domain** models what the platform knows (immutable, side-effect free);
- **Projection Layer** materialises Domain into Read Models;
- **Query DSL** describes *what* to find (intent, not execution).

The Query Engine answers exactly one question:

> **How do I execute an already described query?**

It does not describe queries. It does not build Projections. It does not
work directly with Infrastructure. It is the bridge between a declarative
intent document (KnowledgeQuery) and a concrete data access strategy
(InMemoryStrategy today, PostgreSQL/Neo4j/Elastic strategies in the future).

**It is responsible for:**

- planning — transforming a `KnowledgeQuery` into an `ExecutionPlan`;
- executing — running the plan through a strategy against `ProjectionQueryService`;
- assembling — collecting results into an immutable `QueryResult` with
  the requested shape and explainability.

**It is not responsible for:**

- describing queries (delegated to v2.1.2 Query DSL);
- building Projections (delegated to v2.1.1 Projection Layer);
- persisting data or implementing storage (delegated to v2.1.4 Infrastructure);
- cost-based optimisation, distributed execution, caching (all v2.1.4+).

---

## 2. Public API

```
query_engine/
├── knowledge_query_engine.py   # KnowledgeQueryEngine (facade)
├── query_planner.py            # QueryPlanner
├── execution_plan.py           # ExecutionPlan, ResolutionStep
├── projection_resolver.py      # ProjectionResolver
├── execution_strategy.py       # ExecutionStrategy (Protocol), InMemoryStrategy
├── query_result.py             # QueryResult, QueryMetadata
├── result_assembler.py         # ResultAssembler
├── execution_context.py        # ExecutionContext
└── exceptions.py               # QueryEngineError hierarchy
```

### Key types

| Symbol | Kind | Description |
|--------|------|-------------|
| `KnowledgeQueryEngine` | Service | Main facade — single public entry point |
| `QueryPlanner` | Service | Transforms `KnowledgeQuery` → `ExecutionPlan`. Deterministic, no execution |
| `ExecutionPlan` | Model | Immutable description of execution (target, predicate, steps, shape) |
| `ResolutionStep` | Value Object | Single step: resolves one `QueryTarget` with dependencies |
| `ProjectionResolver` | Service | Determines required Projections from QueryTarget dependencies. **NO store access** |
| `ExecutionStrategy` | Protocol | Abstraction over data access (`execute(plan) → tuple[Projection]`) |
| `InMemoryStrategy` | Service | In-memory implementation via `ProjectionQueryService` |
| `QueryResult` | Model | Immutable result (projections, explainability, metadata) |
| `QueryMetadata` | Value Object | Result metadata (count, time, resolve order) |
| `ResultAssembler` | Service | Assembles `QueryResult` from resolved projections |
| `ExecutionContext` | Value Object | Immutable context (plan + strategy + explainability mode) |

### Exceptions

| Exception | Description |
|-----------|-------------|
| `QueryEngineError` | Base error |
| `PlanningError` | Query planning failed |
| `ExecutionError` | Query execution failed |
| `ResolutionError` | Projection resolution failed |
| `UnsupportedStrategyError` | Strategy not configured or incompatible |
| `ResultAssemblyError` | Result assembly failed |

---

## 3. Dependency Rules

```
v2.1.4 Infrastructure (Store impl., Adapters, Indexes, Caching)
    ↑
────────────────────────────────────────────────
v2.1.3 Query Engine
────────────────────────────────────────────────
    ↑                       ↑
v2.1.2 Query DSL    v2.1.1 Projection Layer
    ↑                       ↑
────────────────────────────────────────────────
v2.0 Domain (Frozen)
────────────────────────────────────────────────
```

**Inside the Query Engine:**

```
KnowledgeQuery (from v2.1.2 DSL)
    │
    ▼
KnowledgeQueryEngine (facade)
    │
    ├── 1. QueryValidator.validate(query)     ← v2.1.2 DSL
    │
    ├── 2. QueryPlanner.plan(query)
    │         │
    │         └── ProjectionResolver.resolve(query)
    │               │
    │               └── ExecutionPlan
    │
    ├── 3. ExecutionStrategy.execute(plan)
    │         │
    │         └── ProjectionQueryService (from v2.1.1)
    │               │
    │               └── tuple[Projection, ...]
    │
    └── 4. ResultAssembler.assemble(query, projections)
              │
              └── QueryResult
```

**Rules:**

- `KnowledgeQueryEngine` depends on: `QueryPlanner`, `ExecutionStrategy`, `ResultAssembler`
- `QueryPlanner` depends on: `ProjectionResolver`
- `ProjectionResolver` depends on: nothing (static dependency map)
- `ExecutionStrategy` (Protocol) depends on: `ExecutionPlan`, `ProjectionQueryService`
- `InMemoryStrategy` depends on: `ProjectionQueryService` (from Projection Layer)
- `ResultAssembler` depends on: `QueryResult`
- **Engine never imports or knows about Domain**
- **Engine never imports infrastructure** (SQL, Neo4j, Elastic)

---

## 4. Architectural Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Deterministic** | Same `KnowledgeQuery` → same `ExecutionPlan` every time |
| 2 | **Stateless** | Engine holds no state between calls |
| 3 | **Immutable Plans** | `ExecutionPlan` is `@dataclass(frozen=True)` — never modified after creation |
| 4 | **Strategy Based** | Execution is exclusively through `ExecutionStrategy` Protocol |
| 5 | **Projection First** | Engine works only with Projection Layer; never directly with Domain |
| 6 | **Infrastructure Agnostic** | No SQL, Neo4j, Elastic, or any storage technology |
| 7 | **Explainability Preserving** | Explainability request flows through entire pipeline without loss |
| 8 | **Separation of Planning and Execution** | Planner plans, Strategy executes, Assembler assembles — each exclusively |
| 9 | **Single Responsibility** | Each component has exactly one concern |
| 10 | **Open for Extension** | New strategies addable without changing Engine |

### 4.1. The Execution Pipeline Invariant

```
KnowledgeQuery
    ↓  (validation — structure only)
ExecutionPlan
    ↓  (strategy — data access)
tuple[Projection]
    ↓  (assembly — result shaping)
QueryResult
```

Each stage is isolated. No stage skips to another layer.
Planner does not execute. Strategy does not plan. Assembler does neither.

---

## 5. Execution Lifecycle

```
KnowledgeQuery { target, predicate, return_shape, explainability }
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 1. ValidatedQueryTarget (via QueryValidator.validate)    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 2. QueryPlanner.plan(query)                              │
│      │                                                   │
│      └── ProjectionResolver.resolve(query)               │
│            │                                              │
│            └── ResolutionStep[ENTITY, AGREEMENT, ...]    │
│                                                           │
│    Output: ExecutionPlan                                  │
│      - target (QueryTarget)                               │
│      - predicate (QueryPredicate | None)                  │
│      - return_shape (ReturnShape)                         │
│      - explainability (ExplainabilityLevel)               │
│      - resolution_steps (tuple[ResolutionStep])           │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 3. ExecutionStrategy.execute(plan)                        │
│      │                                                   │
│      ├── For each ResolutionStep:                        │
│      │     resolve Projection from QueryService          │
│      │                                                   │
│      ├── Filter by predicate tree                        │
│      │     (AND / OR / NOT / Comparison / Exists / In)   │
│      │                                                   │
│    Output: tuple[Projection, ...]                        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 4. ResultAssembler.assemble(query, projections)           │
│      │                                                   │
│      ├── Apply ReturnShape (FULL / FIELDS / SUMMARY /    │
│      │     IDENTIFIERS_ONLY)                              │
│      ├── Collect Explainability (NONE / SUMMARY / FULL)  │
│      ├── Build QueryMetadata (count, time, order)        │
│      │                                                   │
│    Output: QueryResult                                    │
│      - query (KnowledgeQuery)                             │
│      - projections (tuple[Projection])                    │
│      - explainability (tuple[str])                        │
│      - metadata (QueryMetadata)                           │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Out of Scope

The following concerns intentionally do **not** belong to the Query Engine
and are **excluded** from this contract:

- PostgreSQL, Neo4j, Elastic or any concrete database
- Repository implementation
- Transactions
- Caching (any level)
- Indexes and index selection
- Cost-based optimisation
- Distributed execution
- Async / parallel execution
- Background jobs
- Network I/O
- Result pagination
- Sorting (ordering is a Query DSL concern, not Engine)
- Aggregation functions (COUNT, SUM, AVG — belong to Query DSL)
- Full-text search
- Graph traversal algorithms (BFS, DFS, shortest path)
- Schema management
- Migrations
- Configuration
- Authentication / Authorization
- Monitoring / Metrics
- Logging
- Error recovery / retry logic

All of the above belong to v2.1.4 Infrastructure or higher layers.

---

> **Tag:** `v2.1.3-query-engine.done`
>
> **Domain v2.0 frozen. Projection Layer complete. Query DSL complete.**
> **Query Engine is the last pre-infrastructure layer.**
>
> Tests: 32 engine + 886 total ✅
