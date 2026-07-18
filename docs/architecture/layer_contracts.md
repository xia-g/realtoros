# Layer Contracts

## Domain Layer (v2.0)

| Aspect | Contract |
|--------|----------|
| **Input** | OCR result → NormalizedDocument |
| **Output** | BusinessFact, CanonicalEntity, Agreement, KnowledgeGraph, KnowledgeRevision |
| **May import** | Nothing (stdlib only) |
| **May NOT** | Import Projection, Query, Engine, Infrastructure, SQL |
| **Source of truth** | YES — the only source of truth in the platform |
| **Persistence** | Append-only event log (BusinessFacts, Revisions) |
| **Invariants** | Facts immutable, Revisions monotonic, Graph deterministic |

---

## Projection Layer (v2.1.1)

| Aspect | Contract |
|--------|----------|
| **Input** | KnowledgeRevision, Domain models |
| **Output** | Projection (immutable DTO) |
| **May import** | Domain |
| **May NOT** | Import Query, Engine, Infrastructure, know about Store implementation |
| **Source of truth** | NO — fully rebuildable from Domain |
| **Persistence** | Replace-only Store (idempotent, no merge/patch) |
| **Invariants** | Projection NEVER depends on another Projection. Bit-identical for same revision + schema. |

---

## Query Layer (v2.1.2)

| Aspect | Contract |
|--------|----------|
| **Input** | User/AI intent (declarative) |
| **Output** | KnowledgeQuery (Intent Document) |
| **May import** | Domain (subject types, predicate registry) |
| **May NOT** | Import Engine, Projection, Store, Infrastructure, SQL |
| **Source of truth** | NO — describes intent, never execution |
| **State** | Immutable — every modification returns new instance |
| **Invariants** | Query serializable, technology-independent, domain-agnostic core |

---

## Engine Layer (v2.1.3)

| Aspect | Contract |
|--------|----------|
| **Input** | KnowledgeQuery |
| **Output** | ExecutionPlan → KnowledgeResult |
| **May import** | Domain, Projection, Query |
| **May NOT** | Import Infrastructure, SQL, Cypher, backend adapters |
| **Source of truth** | NO — plans are computed, never stored as source |
| **State** | Stateless — same query + same revision → same plan |
| **Invariants** | Planner never executes. Optimizer never changes semantics. Explainability survives optimization. |

---

## Infrastructure Layer (v2.1.4 — future)

| Aspect | Contract |
|--------|----------|
| **Input** | ExecutionPlan |
| **Output** | KnowledgeResult (populated with data) |
| **May import** | Everything (Domain, Projection, Query, Engine) |
| **May NOT** | Be imported by Domain, Projection, Query, Engine |
| **Source of truth** | NO — adapters only |
| **Persistence** | Depends on adapter (PostgreSQL, Neo4j, Elastic, Redis) |
