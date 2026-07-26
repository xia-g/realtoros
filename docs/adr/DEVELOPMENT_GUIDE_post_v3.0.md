# Development Guide — Post v3.0

**Baseline**: v3.0 (frozen)
**Date**: 2026-07-21

## Core Principle

**Default assumption:**

> Every new feature is a Capability — until proven otherwise.

Only when a Proposal demonstrates that v3.0 invariants cannot be preserved,
initiate:

```
ADR → Architecture Review → Baseline v4.x
```

This creates a high cost for Platform changes, protecting the Baseline
from gradual erosion.

## Core Question for Every New Initiative

> **"Can this be implemented as a Capability on top of v3.0,
> or does it require Platform changes?"**

| Answer | Action |
|:------:|--------|
| Yes, Capability only | Proceed with standard Capability pipeline (Proposal → Audit → T1–Tn → Report) |
| Requires Platform change | Separate architecture program: new Baseline + explicit ADR |

## What v3.0 Already Provides

### Read / Analyze (7 capabilities)

```
Explorer      locate     — GET /knowledge/revisions/{id}
Timeline      navigate   — GET /knowledge/documents/{id}/timeline
Diff          compare    — GET /knowledge/revisions/{left}/diff/{right}
Search        find       — GET /knowledge/search
Traversal     connect    — GET /knowledge/traversal
Audit Trail   explain    — GET /knowledge/audit/{id}
Trust State   evaluate   — GET /knowledge/trust/{id}
```

### Decide / Control (2 capabilities)

```
Governance    decide     — GET /knowledge/governance/check/{id}
Recovery      repair     — POST /knowledge/recovery/execute/{id}  (with Governance gate)
```

### Infrastructure (always available)

```
KnowledgeRevisionRepository   — get, save, get_by_document_id
PostgreSQL persistence        — knowledge_revisions, projection_store
Identity Contract             — (node_type, domain_id) for cross-revision references
Deterministic operations      — same input → same output
```

## Typical Capability Pipeline

```
Idea
  ↓
Proposal (Phase 0, no code)
  ↓
Baseline Compatibility Check
  ↓
GO / NO-GO
  ↓
T1 – Tn (implementation)
  ↓
Acceptance Criteria verified
  ↓
Capability Report
```

## When to Consider Platform Change

A Platform change may be warranted when the requirement:

1. **Cannot be expressed** through existing Domain models
   - e.g., entirely new entity type not derivable from existing knowledge
2. **Requires new storage** with different semantics
   - e.g., graph database, event store, search index
3. **Changes the write model** beyond append-only Revision creation
   - e.g., in-place mutation, transaction across revisions
4. **Introduces new lifecycle** stages not compatible with current metadata
   - e.g., approval workflows, multi-branch revision trees

Each Platform change requires:
- Architecture Review
- ADR documenting trade-offs
- New Baseline version
- Full regression suite

## Current Architecture Principles (stable since v2.3.1)

```
1. Platform frozen — Capability layer evolves independently
2. Immutable history — Revisions are append-only
3. Deterministic operations — All capabilities are pure functions
4. Identity contract — (node_type, domain_id) is the logical key
5. Capability isolation — No capability depends on another's internals
6. Read → Validate → Decide → Change — Sequential operation lifecycle
```
