# RealtorOS v2.0 — Domain Architecture Contract

> **Architectural baseline. Golden standard.**
>
> After `v2.0-domain.complete` any change to the **Domain contract** —
> its principles, invariants, dependencies, public API, or guaranteed behaviour —
> is an architecture change, not an implementation change.
>
> Bug fixes, performance optimisation, and refactoring that preserve the contract
> are not architecture changes and do not require an ADR.

---

## 1. Purpose

**Domain v2.0 defines the immutable knowledge model of the platform.**

It is the single source of truth for:

- what the platform knows about business entities and their relationships;
- how facts evolve into structured knowledge;
- how knowledge origin, explanation, and revision are represented.

It is **deterministic, side-effect free, persistence-agnostic, and executable entirely in memory.**

Domain v2.0 is the foundation layer of the RealtorOS architecture:

> All higher architectural layers depend on Domain; Domain depends on none.

It provides the interfaces, models, and services that every other layer (Projection, Query, Engine, Infrastructure) consumes — but **never** the other way around.

---

## 2. Completed Milestones

| Phase | Description | Tag | Status |
|-------|-------------|-----|--------|
| A1 | Neutral Facts | `v2.0-impl.a1` | ✅ |
| A2.1 | Agreement Domain Model | `v2.0-impl.a2.1` | ✅ |
| A2.2 | Agreement Services | `v2.0-impl.a2.2` | ✅ |
| A3.1 | Canonical Identity Model | `v2.0-impl.a3.1` | ✅ |
| A3.2 | Identity Resolution Services | `v2.0-impl.a3.2` | ✅ |
| A4.1 | Knowledge Evolution Model | `v2.0-impl.a4.1` | ✅ |
| A4.2 | Knowledge Evolution Services | `v2.0-impl.a4.2` | ✅ |
| A5.1 | Knowledge Graph Domain Model | `v2.0-impl.a5.1` | ✅ |
| A5.2 | Knowledge Graph Services | `v2.0-impl.a5.2` | ✅ |
| A5.3.1 | Explainability Domain Model | `v2.0-impl.a5.3.1` | ✅ |
| A5.3.2 | Explainability Services | `v2.0-impl.a5.3.2` | ✅ |
| A5.4.1 | Provenance Domain Model | `v2.0-impl.a5.4.1` | ✅ |
| A5.4.2 | Provenance Services | `v2.0-impl.a5.4.2` | ✅ |
| A5.5.1 | Knowledge Revision Model | `v2.0-impl.a5.5.1` | ✅ |
| A5.5.2 | Knowledge Revision Services | `v2.0-impl.a5.5.2` | ✅ |

---

## 3. Domain Pipeline

```
Documents
    ↓
Business Facts (A1)
    ↓
Agreement (A2)
    ↓
Canonical Identity (A3)
    ↓
Knowledge Evolution (A4)
    ↓
Knowledge Graph (A5.1–A5.2)
    ↓
Explainability (A5.3)
    ↓
Provenance (A5.4)
    ↓
Knowledge Revision (A5.5)
```

Each stage consumes output of the previous stage and produces new immutable value objects.
No stage mutates shared state. No stage performs I/O.

---

## 4. Architectural Principles

1. **Immutable objects only** — every model is `@dataclass(frozen=True)`. No setters, no mutators.
2. **No repositories** — Domain has zero awareness of persistence.
3. **No database** — no SQL, no ORM, no connection strings exist in Domain.
4. **No caching** — Domain is stateless; caching belongs to infrastructure.
5. **No side effects** — calling a Domain service changes nothing except the returned object.
6. **Deterministic algorithms** — same input → same output, always.
7. **Explicit value objects** — every primitive is wrapped in a typed value object.
8. **Pure domain services** — stateless, no injected dependencies, `@staticmethod` where possible.
9. **Append-only knowledge evolution** — knowledge grows; nothing is ever deleted or overwritten.
10. **Explainability by construction** — every knowledge statement carries its explanation and provenance.
11. **Builders coordinate, never decide** — builders call factories; factories create immutable objects.
12. **Integrity checkers observe, never fix** — they return a report; they do not mutate.

---

## 5. Dependency Rules

```
              Knowledge Revision (A5.5)
                      ↓
                Provenance (A5.4)
                      ↓
              Explainability (A5.3)
                      ↓
              Knowledge Graph (A5.1–A5.2)
                      ↓
            Knowledge Evolution (A4)
                      ↓
            Canonical Identity (A3)
                      ↓
                 Agreement (A2)
                      ↓
               Neutral Facts (A1)
```

**Rule:** Dependencies always point downward. No reverse dependencies allowed.

| Layer | May import |
|-------|------------|
| Neutral Facts | — (zero dependencies) |
| Agreement | Facts |
| Identity | Facts |
| Knowledge Evolution | Facts, Agreement, Identity |
| Knowledge Graph | Facts, Agreement, Identity, Evolution |
| Explainability | Graph |
| Provenance | Graph |
| Revision | Graph, Provenance, Explainability |

---

## 6. Public API

### `domain/business_relationship/` — by package

#### Neutral Facts (A1)

| Symbol | Kind | Description |
|--------|------|-------------|
| `BusinessFact` | Model | Immutable fact extracted from document |
| `FactId` | Value Object | Deterministic fact identifier |
| `FactValue` | Value Object | Typed fact value (string, decimal, date) |
| `FactConfidence` | Value Object | Confidence score [0.0–1.0] |
| `FactSource` | Value Object | Source classification (semantic, manual) |
| `FactEvidence` | Value Object | Document reference as evidence |
| `FactBuilder` | Service | Creates BusinessFact from document parts |

#### Agreement (A2)

| Symbol | Kind | Description |
|--------|------|-------------|
| `Agreement` | Model | Immutable agreement record |
| `AgreementId` | Value Object | Agreement identifier |
| `AgreementStatus` | Enum | Active, terminated, expired, draft |
| `AgreementPeriod` | Value Object | Date range with validation |
| `AgreementParticipant` | Value Object | Party with role and optional share/period |
| `AgreementReference` | Value Object | Cross-document reference |
| `AgreementMetadata` | Value Object | Infrastructure fields |
| `AgreementCandidate` | Value Object | Potential match candidate |
| `AgreementMatchResult` | Value Object | Match decision with evidence |
| `AgreementResolutionResult` | Value Object | Resolution output |
| `AgreementResolutionReport` | Value Object | Resolution summary |
| `AgreementMatcher` | Service | Finds matching existing agreements |
| `AgreementResolver` | Service | Resolves documents into agreements |

#### Canonical Identity (A3)

| Symbol | Kind | Description |
|--------|------|-------------|
| `CanonicalEntity` | Model | Immutable canonical entity |
| `CanonicalEntityId` | Value Object | Entity identifier |
| `EntityAlias` | Value Object | Alternative name or identifier |
| `EntityIdentifier` | Value Object | Typed identifier (INN, OGRN, etc.) |
| `IdentityEvidence` | Value Object | Evidence supporting identity |
| `IdentityMetadata` | Value Object | Infrastructure fields |
| `NormalizedIdentifier` | Value Object | Normalized form of identifier |
| `IdentityCandidate` | Value Object | Candidate for resolution |
| `IdentityMatchResult` | Value Object | Match decision |
| `IdentityResolutionResult` | Value Object | Resolution output |
| `IdentityResolutionReport` | Value Object | Resolution summary |
| `Normalization` | Service | Identifier normalisation (INN, OGRN, phone, etc.) |
| `IdentityResolver` | Service | Matches entities by identifiers |

#### Knowledge Evolution (A4)

| Symbol | Kind | Description |
|--------|------|-------------|
| `KnowledgeEvent` | Model | Immutable event record |
| `KnowledgeEventId` | Value Object | Event identifier |
| `KnowledgeEventType` | Enum | created, matched, updated, superseded |
| `KnowledgeChange` | Model | Describes a change to knowledge |
| `KnowledgeDelta` | Model | Collection of changes |
| `KnowledgeConflict` | Model | Immutable conflict description |
| `KnowledgeTimelineEntry` | Model | Timeline record |
| `KnowledgeMetadata` | Value Object | Infrastructure fields |
| `KnowledgeEvolutionResult` | Value Object | Evolution output |
| `KnowledgeEvolutionReport` | Value Object | Evolution summary |
| `TrustLevel` | Enum | unknown, low, medium, high |
| `AuthorityLevel` | Enum | very_low, normal, high, official |
| `ConflictType` | Enum | ownership, participant, data_mismatch |
| `KnowledgeEvolutionService` | Service | Registers events, manages evolution |
| `ConflictDetector` | Service | Detects conflicts between facts |
| `TrustEvaluator` | Service | Evaluates trust based on evidence |
| `AuthorityEvaluator` | Service | Evaluates authority of sources |

#### Knowledge Graph (A5.1–A5.2)

| Symbol | Kind | Description |
|--------|------|-------------|
| `KnowledgeGraph` | Model | Immutable graph of nodes and edges |
| `GraphNode` | Model | Immutable graph node |
| `GraphEdge` | Model | Immutable graph edge |
| `GraphNodeId` | Value Object | Deterministic node identifier |
| `GraphEdgeId` | Value Object | Deterministic edge identifier |
| `GraphNodeType` | Enum | ENTITY, AGREEMENT, FACT, PROPERTY, DOCUMENT |
| `GraphEdgeType` | Enum | various typed relationships |
| `GraphAttributes` | Value Object | Node/edge metadata |
| `GraphMetadata` | Value Object | Infrastructure fields |
| `GraphBuildResult` | Value Object | Build output |
| `GraphBuildReport` | Value Object | Build summary |
| `GraphNodeFactory` | Service | Creates GraphNode from domain objects |
| `GraphEdgeFactory` | Service | Creates GraphEdge from domain objects |
| `GraphBuilder` | Service | Builds KnowledgeGraph from domain data |
| `GraphIntegrityChecker` | Service | Validates graph structure |

#### Explainability (A5.3)

| Symbol | Kind | Description |
|--------|------|-------------|
| `GraphExplanation` | Model | Immutable explanation record |
| `ExplanationId` | Value Object | Explanation identifier |
| `ExplanationReason` | Model | Reason with type and description |
| `ExplanationEvidence` | Model | Supporting evidence reference |
| `ExplanationStep` | Model | Step in explanation chain |
| `ExplanationMetadata` | Value Object | Infrastructure fields |
| `ExplanationReasonType` | Enum | direct_match, inferred, authoritative, default |
| `ExplainabilityResult` | Value Object | Build output |
| `ExplainabilityReport` | Value Object | Build summary |
| `ExplanationReasonFactory` | Service | Creates ExplanationReason |
| `ExplanationEvidenceFactory` | Service | Creates ExplanationEvidence |
| `ExplanationBuilder` | Service | Builds GraphExplanation |
| `ExplanationIntegrityChecker` | Service | Validates explanation structure |

#### Provenance (A5.4)

| Symbol | Kind | Description |
|--------|------|-------------|
| `KnowledgeProvenance` | Model | Immutable provenance record |
| `ProvenanceId` | Value Object | Provenance identifier |
| `ProvenanceSource` | Model | Source of knowledge |
| `ProvenanceSourceType` | Enum | document, fact, agreement, entity, event |
| `ProvenanceLink` | Model | Link between node and source |
| `ProvenanceChain` | Model | Ordered chain of provenance links |
| `ProvenanceMetadata` | Value Object | Infrastructure fields |
| `ProvenanceResult` | Value Object | Build output |
| `ProvenanceReport` | Value Object | Build summary |
| `ProvenanceSourceFactory` | Service | Creates ProvenanceSource |
| `ProvenanceLinkFactory` | Service | Creates ProvenanceLink |
| `ProvenanceBuilder` | Service | Builds KnowledgeProvenance |
| `ProvenanceIntegrityChecker` | Service | Validates provenance structure |

#### Knowledge Revision (A5.5)

| Symbol | Kind | Description |
|--------|------|-------------|
| `KnowledgeRevision` | Model | Immutable snapshot of knowledge at a point in time |
| `KnowledgeRevisionId` | Value Object | Revision identifier |
| `KnowledgeRevisionNumber` | Value Object | Monotonic revision number |
| `KnowledgeSnapshot` | Model | Snapshot of Graph + Provenance + Explanation |
| `KnowledgeRevisionMetadata` | Value Object | Infrastructure fields |
| `RevisionReference` | Model | Parent/derived link between revisions |
| `KnowledgeRevisionResult` | Value Object | Build output |
| `KnowledgeRevisionReport` | Value Object | Build summary |
| `RevisionIntegrityReport` | Value Object | Integrity check results |
| `RevisionSnapshotFactory` | Service | Creates KnowledgeSnapshot |
| `RevisionReferenceFactory` | Service | Creates RevisionReference |
| `RevisionBuilder` | Service | Coordinates revision construction |
| `RevisionIntegrityChecker` | Service | Validates revision structure |

---

## 7. Domain Guarantees

The following guarantees are provided by the Domain architecture:

| Guarantee | Description |
|-----------|-------------|
| **Deterministic execution** | Same input → same output. No randomness in business logic. |
| **Immutable state** | No Domain object is ever modified after creation. |
| **Referential transparency** | Any Domain expression can be replaced with its value without changing behaviour. |
| **Replayable revisions** | Given the same facts and events, the same revision is produced. |
| **Provenance completeness** | Every knowledge statement carries its origin chain. |
| **Explainability completeness** | Every graph node has an explanation of how it was derived. |
| **Stable identifiers** | Graph node IDs and fact IDs are deterministically computed, never random. |
| **Versioned evolution** | Every change to knowledge is recorded as an event — no silent mutations. |
| **No data loss** | Conflicts preserve both sides; superseded knowledge is never deleted. |
| **Zero infrastructure coupling** | Domain runs in pure memory, no imports from outside. |

---

## 8. ADR Index

### Architecture Freeze v1 (ADR-001–ADR-015)

| ADR | Title |
|-----|-------|
| 0001 | PostgreSQL |
| 0002 | Canonical Domain Model |
| 0003 | ER Model v1 |
| 0004 | OCR Layer (PaddleOCR) |
| 0005 | Document Classifier |
| 0006 | Entity Extraction |
| 0007 | Entity Resolution |
| 0008 | Knowledge Graph |
| 0009 | Embedding Storage and Metadata |
| 0010 | Soft Delete and Audit |
| 0011 | Knowledge Agent v1 |
| 0012 | Architecture Freeze v1 |
| 0013 | Lead Management Model |
| 0014 | Telegram Staff Assistant v1 |
| 0015 | Knowledge Agent Runtime v1 |

### Architecture Freeze v2

| ADR | Title |
|-----|-------|
| ADR-013 | Ledger Boundary |
| ADR-014 | Tax Assignment Layer |
| ADR-015 | Report Is Generated Artifact |

---

## 9. Statistics

### Domain

| Category | Count |
|----------|-------|
| Value Objects | ~40 |
| Domain Models | ~25 |
| Domain Services | ~22 |
| Enums | ~12 |
| Protocols / ABCs | 0 (no abstraction layer needed) |
| Total Python files (`domain/business_relationship/`) | 115 |
| Total lines of code (`domain/business_relationship/`) | 6,788 |

### Tests

| Category | Count |
|----------|-------|
| Test files (A1–A5.5) | 14 |
| Tests (business_relationship) | 626 ✅ |
| Tests (entire project) | 756 ✅ |
| Test lines of code | 4,173 |

### Architecture

| Category | Count |
|----------|-------|
| Architecture Freeze versions | 2 (v1, v2) |
| ADR documents | 19 |
| Architecture documents | 5 (overview, dependencies, invariants, layer contracts, terminology) |
| Git tags (v2.0) | 16 (15 phases + 1 final) |
| Pipeline stages | 9 (Document → Revision) |

---

## 10. Out of Scope

The following concerns intentionally do **not** belong to Domain and are **excluded** from this contract:

- persistence
- SQL
- Neo4j
- Elastic
- repositories
- projections
- query execution
- indexing
- caching
- transactions
- infrastructure
- user interfaces
- network protocols
- serialization formats (JSON, Protobuf)
- file I/O
- logging
- monitoring
- authentication
- authorization
- configuration
- secrets management
- dependency injection
- event buses
- message queues
- API gateways
- rollback logic
- merge logic
- diff computation
- search algorithms
- graph traversal (BFS, DFS, shortest path)

---

## 11. After Freeze

After the tag `v2.0-domain.complete`:

```
                    v2.2+ Applications
                           │
                    Query Engine
                           │
                     Query DSL
                           │
                  Projection Layer
                           │
────────────────────────────────────────
             Domain v2.0 (Frozen)
────────────────────────────────────────
```

Domain v2.0 defines the semantic model of knowledge. Starting with v2.1,
the project builds access mechanisms for this model (Projection, Query DSL,
Query Engine). A frozen Domain allows developing these layers without
constantly re‑negotiating the foundation.

**Architecture change** is a change to the **Domain contract** —
its principles, invariants, dependencies, public API, or guaranteed behaviour.

**Not an architecture change** (no ADR needed):

- bug fix that preserves the contract;
- performance optimisation without changing observable behaviour;
- refactoring that preserves public API;
- adding tests;
- documentation.

### The following require a **new ADR** and explicit freeze exception

1. Adding a new field to any existing model
2. Removing or renaming any existing field
3. Adding a new model or value object
4. Adding a new domain service
5. Changing the pipeline (order of stages, input/output of any service)
6. Adding a new dependency between modules
7. Changing any enum member set
8. Changing validation rules (e.g. confidence range, revision number constraints)
9. Changing the semantics of equality or hashing for any value object

### Architectural Decision Matrix

| Change | Requires ADR | Minor version | Major version |
|--------|:------------:|:-------------:|:-------------:|
| New `@dataclass(frozen=True)` Value Object (no API change) | ❌ | ❌ | ❌ |
| New Enum member (backward-compatible) | ❌ | ❌ | ❌ |
| New Domain Service (pure, existing API unchanged) | ❌ | ✅ | ❌ |
| New Domain Model (immutable, no existing API change) | ❌ | ✅ | ❌ |
| New method on existing Service | ✅ | ✅ | ❌ |
| New public export from Domain package | ✅ | ✅ | ❌ |
| Adding optional parameter (backward-compatible) | ❌ | ✅ | ❌ |
| Adding required parameter to existing method | ✅ | ❌ | ✅ |
| Changing type of existing field | ✅ | ❌ | ✅ |
| Removing existing field or method | ✅ | ❌ | ✅ |
| Renaming existing public symbol | ✅ | ❌ | ✅ |
| Changing validation rules (confidence range, number constraints) | ✅ | ❌ | ✅ |
| Changing equality/hash semantics | ✅ | ❌ | ✅ |
| Removing Enum member | ✅ | ❌ | ✅ |
| Changing dependency direction (upward) | ✅ | ❌ | ✅ |
| Breaking pipeline order (inputs/outputs of existing service) | ✅ | ❌ | ✅ |
| Adding infrastructure dependency (import from outside Domain) | ✅ | ❌ | ✅ |
| Changing Architectural Principles (section 4) or Invariants | ✅ | ❌ | ✅ |
| Bug fix preserving semantics | ❌ | ❌ | ❌ |
| Adding tests | ❌ | ❌ | ❌ |
| Documentation | ❌ | ❌ | ❌ |
| Performance optimisation (preserved interface) | ❌ | ❌ | ❌ |
| Refactoring internals (preserved public API) | ❌ | ❌ | ❌ |

**Legend:**

- **ADR** — Architecture Decision Record must be written and reviewed
- **Minor version** — increment minor version number (e.g. `v2.1`)
- **Major version** — increment major version number (e.g. `v3.0`)
- **❌** — not required

**Rule of thumb:** If a change could break a consumer of the Domain API, it requires a major version.
If it adds new capabilities without breaking anything, it requires a minor version.
If it only touches implementation internals, no version change is needed.
Any architectural change (non-local impact, change to invariants, new dependency direction)
requires an ADR regardless of version.

### Enforcement

```python
# Example: Domain must not import infrastructure
def test_domain_does_not_import_infrastructure():
    import sys
    assert "sqlalchemy" not in sys.modules
    assert "psycopg2" not in sys.modules
```

---

> **Golden Baseline**
>
> Tag: `v2.0-domain.complete`
>
> Date: 2026-07-08
>
> Pipeline: Documents → Facts → Agreement → Identity → Evolution → Graph → Provenance → Explainability → Revision
>
> Files: 115 domain / 14 test | LOC: 6,788 domain / 4,173 test | Tests: 626 domain / 756 total
