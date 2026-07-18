# RealtorOS Invariants

**All 35 architectural invariants across all layers.**

## Domain Invariants (v2.0)

| # | Invariant |
|---|-----------|
| D1 | BusinessFact is immutable — `@dataclass(frozen=True)`, never mutated after creation |
| D2 | Facts do not interpret business — DOCUMENT_HAS_*, not SELLS/OWNS |
| D3 | KnowledgeGraph is pure domain abstraction — not Neo4j, not a DB |
| D4 | All graph edges validated against GraphSchema — invalid edges rejected |
| D5 | All graph nodes have deterministic stable IDs — `ENTITY:{id}` not random UUID |
| D6 | GraphBuilder is single entry point — no manual node/edge creation |
| D7 | KnowledgeRevision is immutable, monotonic, append-only |
| D8 | KnowledgeState computed from Domain only — no manual changes |
| D9 | ConfidenceHistory is append-only — trust never decreases automatically |
| D10 | Conflict preserves both values — no automatic data loss |

## Projection Invariants (v2.1.1)

| # | Invariant |
|---|-----------|
| P1 | Projection is never source of truth — Domain wins on conflict |
| P2 | Projection may only be derived from Domain state |
| P3 | Neither Builders nor Projections may use another Projection as input |
| P4 | Store is replace-only — no merge, no patch, no partial update |
| P5 | BuildPlan is declarative — no callables, no executable code |
| P6 | Plan describes WHAT, Executor decides HOW — Plan never executes |
| P7 | Domain never imports Projection — zero coupling |
| P8 | Projection is deterministic — same revision + schema → bit-identical |
| P9 | Projection is fully rebuildable — same input → same output |
| P10 | ProjectionVersion = f(knowledge_revision, schema_version) — nothing else |

## Query Invariants (v2.1.2)

| # | Invariant |
|---|-----------|
| Q1 | Query describes intent, never execution |
| Q2 | Query is technology-independent — same query works on any backend |
| Q3 | Query is fully serializable — Intent Document in JSON |
| Q4 | Query is deterministic — same query + revision → identical result |
| Q5 | Query never mutates Domain — read-only, no side effects |
| Q6 | Query core is domain-agnostic — PredicateRegistry provides semantics |
| Q7 | Query is immutable — `with_predicate()` returns a NEW instance |
| Q8 | Query result is immutable — KnowledgeResult is frozen |
| Q9 | Query can explain itself — `Explain()` returns QueryExplanation[] |
| Q10 | Query validation is separate from execution — no backend needed |
| Q11 | Query knows graph semantics (PathBetween), not graph algorithms (BFS) |
| Q12 | Query doesn't know about Projections or Store — Planner resolves |

## Engine Invariants (v2.1.3)

| # | Invariant |
|---|-----------|
| E1 | Engine never changes Domain |
| E2 | Planner describes execution, never executes |
| E3 | Optimizer never changes query semantics — optimized plan ≡ original |
| E4 | ExecutionPlan is deterministic — same query + revision → same plan |
| E5 | ExecutionPlan is technology-independent — no SQL, no Cypher, no backend refs |
| E6 | Projection resolution is transparent to Query |
| E7 | Explainability survives optimization — all annotations preserved |
| E8 | Result assembly is deterministic |
| E9 | Engine never depends on infrastructure — operates on interfaces only |
| E10 | Failed stage can be retried without side effects |
