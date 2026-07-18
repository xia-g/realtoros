# RealtorOS v2.1 — Application Core Completion

> **Golden baseline of the complete application core.**
>
> Tag: `v2.1.complete`
>
> Architecture Freeze v2.1 — technology-agnostic, persistence-agnostic,
> ready for concrete infrastructure implementations.

---

## 1. Purpose

**v2.1 defines the complete application core of the Knowledge Platform.**

It is:

- **technology agnostic** — no dependency on any specific database, framework,
  or infrastructure technology;
- **persistence agnostic** — all storage interactions go through Protocols,
  never through concrete implementations;
- **ready for concrete infrastructure** — the core can be deployed with
  in-memory adapters immediately; real databases connect via the same
  Protocols without changing a single line above Infrastructure.

From v2.1 forward, the core is **architecturally closed**:

> All higher layers (v2.2+, applications) depend on v2.1;
> v2.1 depends on nothing external.

---

## 2. Layer Stack

```
┌─────────────────────────────────────────────────────┐
│               v2.1.4 Infrastructure                 │
│  MemoryStore  |  InMemoryStrategy                   │
│  (Future: PostgreSQL | Neo4j | Elastic)              │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              v2.1.3 Knowledge Query Engine          │
│  Planner  →  Strategy  →  Assembler                  │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│            v2.1.2 Knowledge Query DSL               │
│  KnowledgeQuery  |  Predicate Tree  |  ReturnShape   │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│             v2.1.1 Projection Layer                 │
│  Coordinator  →  Builder  →  Store Protocol          │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              v2.0 Domain (Frozen)                   │
│  Facts → Agreement → Identity → Evolution →        │
│  Graph → Explainability → Provenance → Revision     │
└─────────────────────────────────────────────────────┘
```

---

## 3. Layer Contracts

### v2.0 Domain (Frozen)

The Domain defines the immutable knowledge model of the platform.
It is deterministic, side-effect free, persistence-agnostic,
and executable entirely in memory. No layer above may modify Domain.
Domain imports nothing.

**Tag:** `v2.0-domain.complete`
**Files:** 115 | **Tests:** 626

### v2.1.1 Projection Layer

Materialises immutable Domain objects into immutable Read Models.
The **Builder** is the only component that reads Domain.
The **Store** is a Protocol — no storage implementation exists here.
The **Coordinator** orchestrates via Registry and Store Protocol.
No business logic, no query logic, no infrastructure.

**Tag:** `v2.1.1-projections.complete`
**Files:** 11 | **Tests:** 40

### v2.1.2 Knowledge Query DSL

A declarative query intent language.
Describes *what* to find, never *how* to execute.
All types are immutable, typed, and composition-friendly.
KnowledgeQuery knows nothing about Store, Planner, Engine, or Projections.

**Tag:** `v2.1.2-query-dsl.done`
**Files:** 11 | **Tests:** 58

### v2.1.3 Knowledge Query Engine

The first layer with execution behaviour.
Plans queries into immutable `ExecutionPlan`s, executes through
`ExecutionStrategy` Protocol, assembles results into `QueryResult`.
Planner does not execute. Strategy does not plan. Assembler does neither.
Zero infrastructure dependencies.

**Tag:** `v2.1.3-query-engine.done`
**Files:** 10 | **Tests:** 32

### v2.1.4 Infrastructure Adapters

Implements existing Protocols. Creates no new architectural concepts.
`MemoryProjectionStore` and `InMemoryExecutionStrategy` serve as
behavioural references. `CompositionRoot` is the single point where
concrete adapters are wired. Future PostgreSQL/Neo4j/Elastic adapters
plug in via the same Protocols without changing the core.

**Tag:** `v2.1.4-infrastructure.done`
**Files:** 8 | **Tests:** 21

---

## 4. Dependency Rules

```
                    ┌──────────────────────┐
                    │  v2.1.4 Infrastructure│
                    │  depends on: all above│
                    │  imported by: nothing │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  v2.1.3 Query Engine │
                    │  depends on: DSL,    │
                    │  Projection Layer    │
                    │  imported by: Infra  │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  v2.1.2 Query DSL    │
                    │  depends on: nothing │
                    │  imported by: Engine │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  v2.1.1 Projection   │
                    │  depends on: Domain  │
                    │  imported by: Engine │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  v2.0 Domain (Frozen)│
                    │  depends on: nothing │
                    │  imported by: all    │
                    └──────────────────────┘
```

**Cardinal rule:** Dependencies always point downward.
No layer imports a layer above itself. Infrastructure may import all;
Domain imports nothing.

---

## 5. Public APIs

### Package: `domain/business_relationship/` (v2.0)

See `DOMAIN_COMPLETION.md` section 6 for the full 100+ symbol listing.

Key sub-packages:

```
domain/business_relationship/
├── Neutral Facts         (A1):  BusinessFact, FactId, FactValue, FactBuilder
├── Agreement             (A2):  Agreement, AgreementId, AgreementMatcher, AgreementResolver
├── Canonical Identity    (A3):  CanonicalEntity, IdentityResolver, Normalization
├── Knowledge Evolution   (A4):  KnowledgeEvent, KnowledgeEvolutionService, ConflictDetector
├── Knowledge Graph   (A5.1–2):  KnowledgeGraph, GraphNode, GraphBuilder, GraphIntegrityChecker
├── Explainability   (A5.3):    GraphExplanation, ExplanationBuilder
├── Provenance       (A5.4):    KnowledgeProvenance, ProvenanceBuilder
└── Knowledge Revision (A5.5):  KnowledgeRevision, RevisionBuilder
```

### Package: `projection/` (v2.1.1)

| Symbol | Kind | Description |
|--------|------|-------------|
| `Projection` | Protocol | Base Read Model |
| `ProjectionId` | VO | Immutable identifier |
| `ProjectionType` | Enum | ENTITY, AGREEMENT, OWNERSHIP, TIMELINE, GRAPH, RISK, PROVENANCE |
| `BuildPlan` | Model | Declarative plan — no bool flags |
| `BuildStep` | VO | Single step with dependencies |
| `ProjectionBuilder` | Protocol | Domain → Projection transform |
| `ProjectionRegistry` | Service | Type → Builder map |
| `ProjectionCoordinator` | Service | Orchestrator |
| `ProjectionStore` | Protocol | put/get/remove/contains |
| `ProjectionQueryService` | Service | Read-only API |
| `ProjectionDigest` | VO | Deterministic freshness check |
| `StalenessService` | Service | Fresh / Stale / Missing |

### Package: `query/` (v2.1.2)

| Symbol | Kind | Description |
|--------|------|-------------|
| `KnowledgeQuery` | Model | Main immutable query intent |
| `QueryTarget` | Enum | 7 projection target types |
| `Predicate` | Union | ComparisonPredicate, ExistsPredicate, InPredicate |
| `PredicateOperator` | Enum | 11 operators (EQUALS..IN) |
| `And`, `Or`, `Not` | Model | Immutable predicate composition |
| `PropertyReference` | VO | Typed field reference, no raw strings |
| `LiteralValue` | Union | 7 typed literal types |
| `ReturnShape` | Model | FULL, FIELDS, SUMMARY, IDENTIFIERS_ONLY |
| `ExplainabilityLevel` | Enum | NONE, SUMMARY, FULL |
| `QueryValidator` | Service | Structural validation, no execution |

### Package: `query_engine/` (v2.1.3)

| Symbol | Kind | Description |
|--------|------|-------------|
| `KnowledgeQueryEngine` | Service | Main facade |
| `QueryPlanner` | Service | Creates ExecutionPlan |
| `ExecutionPlan` | Model | Immutable execution description |
| `ResolutionStep` | VO | Single resolution step |
| `ProjectionResolver` | Service | Dependency resolution |
| `ExecutionStrategy` | Protocol | Execute plan |
| `InMemoryStrategy` | Service | Reference implementation |
| `QueryResult` | Model | Immutable result |
| `QueryMetadata` | VO | Result metadata |
| `ResultAssembler` | Service | Assembles QueryResult |
| `ExecutionContext` | VO | Immutable context |

### Package: `infrastructure/` (v2.1.4)

| Symbol | Kind | Description |
|--------|------|-------------|
| `MemoryProjectionStore` | Service | Reference ProjectionStore impl |
| `InMemoryExecutionStrategy` | Service | Reference Strategy impl |
| `ProjectionCodec` | Service | Encode/decode Projections |
| `ProjectionData` | VO | Serializable projection data |
| `ConnectionProvider` | Protocol | DB connection (future) |
| `TransactionManager` | Protocol | DB transactions (future) |
| `AdapterConfiguration` | VO | Declarative config |
| `ProjectionStoreFactory` | Service | Store from config |
| `ExecutionStrategyFactory` | Service | Strategy from config |
| `KnowledgeQueryEngine` | Service | DI-wired Engine |

---

## 6. Architectural Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Immutable by default** | All models, plans, results are `@dataclass(frozen=True)` |
| 2 | **Protocol first** | Every boundary between layers is a Protocol |
| 3 | **Dependency inversion** | High-level layers define Protocols; Infrastructure implements |
| 4 | **Technology agnostic** | Zero dependency on any database, framework, or infrastructure |
| 5 | **Explainability preserving** | Explainability request flows through entire pipeline without loss |
| 6 | **Deterministic** | Same input → same output at every layer |
| 7 | **Stateless execution** | No layer holds state between calls |
| 8 | **Pure Domain** | Domain has zero awareness of anything above it |
| 9 | **Composition Root only** | Concrete adapter wiring is a single, isolated point |
| 10 | **Replaceable adapters** | Any Protocol implementation can be swapped without changing the core |
| 11 | **Separation of concerns** | Planner plans, Strategy executes, Assembler assembles — each exclusively |
| 12 | **No business logic in infra** | Infrastructure implements storage, never business rules |

---

## 7. Out of Scope

The following concerns intentionally do **not** belong to the v2.1 core
and are delegated to v2.2+ layers:

- REST API
- GraphQL
- gRPC
- Authentication
- Authorization / Permissions
- User management
- Session management
- Messaging / Event bus
- Background workers
- Job scheduling
- Real databases (PostgreSQL, Neo4j, Elastic)
- SQL generation
- Cloud deployment
- Containerisation
- Monitoring
- Metrics / Tracing
- Logging infrastructure
- CI/CD
- Testing infrastructure (integration, E2E)
- API versioning
- Rate limiting
- Caching (application-level)
- File storage
- Email / Notifications
- Webhooks
- Audit logging (infrastructure-level)

---

## 8. Roadmap — Closing v2.x

```
v2.0 ─── Knowledge Model ─────────────────────────────────────── ✅
        A1–A5.5: Facts, Agreement, Identity, Evolution,
        Knowledge Graph, Explainability, Provenance, Revision
        Tag: v2.0-domain.complete

v2.1 ─── Application Core ────────────────────────────────────── ✅
        Projection Layer  +  Query DSL  +  Query Engine
        +  Infrastructure Adapters (in-memory reference)
        Tag: v2.1.complete

v2.2 ─── Technology Integrations ───────────────────────────────
        PostgreSQLProjectionStore
        Neo4jProjectionStore / Neo4jExecutionStrategy
        ElasticProjectionStore / ElasticExecutionStrategy
        HybridExecutionStrategy
        Real ConnectionProvider implementations
        Real TransactionManager implementations
        Integration tests with real databases

v2.3 ─── Application Services ─────────────────────────────────
        REST API (FastAPI)
        GraphQL endpoint
        Authentication / Authorization
        Background workers
        Event-driven integration
        Admin UI

v3 ─── Distributed Knowledge Platform ─────────────────────────
        Multi-node deployment
        Horizontal scaling
        Read replicas
        Distributed query execution
        Cross-region replication
        Monitoring & Observability
```

---

> **Golden Baseline — Application Core v2.1**
>
> Tag: `v2.1.complete`
>
> Date: 2026-07-08
>
| Layer | Tag | Files | Tests |
|-------|-----|-------|-------|
| Domain v2.0 | `v2.0-domain.complete` | 115 | 626 |
| Projection Layer | `v2.1.1-projections.complete` | 11 | 40 |
| Query DSL | `v2.1.2-query-dsl.done` | 11 | 58 |
| Query Engine | `v2.1.3-query-engine.done` | 10 | 32 |
| Infrastructure | `v2.1.4-infrastructure.done` | 8 | 21 |
| **Total** | **v2.1.complete** | **~155** | **907** ✅ |
