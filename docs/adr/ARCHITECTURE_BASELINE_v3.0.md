# Architecture Baseline v3.0

**Date**: 2026-07-21
**Status**: FROZEN

## Scope

All Platform components frozen since v2.3.1 remain frozen.
Capability layer now contains 10 independently verified capabilities
built entirely on top of the unchanged Platform.

## Baseline Components (unchanged since v2.3.1)

```
Domain (frozen):
  KnowledgeRevision, KnowledgeSnapshot, KnowledgeGraph
  GraphNode, GraphEdge, KnowledgeProvenance, GraphExplanation
  RevisionBuilder, RevisionSnapshotFactory

Persistence (frozen):
  Repository Protocol, PostgreSQLRepository, MemoryRepository
  ProjectionStore Protocol, PostgreSQLProjectionStore, MemoryProjectionStore
  Materialization

Query (frozen):
  Query DSL, Query Planner, Query Engine

Bootstrap (frozen):
  Composition root, lifespan, DI
```

## Capability Layer Summary

| # | Version | Capability | Operation | Tests |
|:-:|:-------:|:-----------|:---------:|:-----:|
| 1 | v2.3.1 | Knowledge Explorer | locate | 7 |
| 2 | v2.3.1 | Knowledge Timeline | navigate | 12 |
| 3 | v2.3.1 | Knowledge Diff Explorer | compare | 41 |
| 4 | v2.3.1 | Knowledge Search | find | 11 |
| 5 | v2.4 | Knowledge Graph Traversal | connect | 8 |
| 6 | v2.5 | Knowledge Consistency Check | validate | 15 |
| 7 | v2.6 | Knowledge Audit Trail | explain | 10 |
| 8 | v2.7 | Knowledge Trust State | evaluate | 14 |
| 9 | v2.8 | Knowledge Governance | decide | 14 |
| 10 | v2.9 | Knowledge Recovery | repair | 10 |
| | | **Total** | | **1106** |

## Key Metrics

```
Platform files changed:   0  (across all 10 capabilities)
ADR required:             0
Architecture Review:      0
Baseline regressions:     0
Total tests:              1106 / 1106 PASS
```

## Architectural Invariants (validated)

```
1. Platform unchanged        — 10 capabilities, 0 Platform files changed
2. Immutable history         — Recovery creates new Revision, never edits
3. Deterministic operations  — Same input → same output for all capabilities
4. Capability isolation      — No capability depends on another's internal state
5. Read-before-write         — Recovery requires Governance → Trust → Consistency
6. Identity contract         — (node_type, domain_id) stable across all capabilities
```

## Capability Dependency Map

```
Explorer (locate)
    |
Timeline (navigate)
    |
    +-- Diff (compare)
    |
    +-- Search (find)
    |
    +-- Traversal (connect)
    |
    +-- Consistency (validate)
    |       |
    |       +-- Audit Trail (explain)
    |       |
    |       +-- Trust State (evaluate)
    |               |
    |               +-- Governance (decide)
    |                       |
    |                       +-- Recovery (repair)
    |
    All → read from existing KnowledgeRevision / KnowledgeSnapshot
```

## What v3.0 Enables

With the Platform validated by 10 independent capabilities, the architecture
is ready for the next wave of development:

- **Policies** — Rule-based knowledge management using Governance
- **Collaboration** — Multi-actor knowledge workflows
- **Distribution** — Cross-node knowledge sharing
- **Intelligence** — ML-assisted knowledge operations
- **Scale** — Performance optimization without architecture changes
