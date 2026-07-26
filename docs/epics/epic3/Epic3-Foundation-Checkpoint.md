# Epic 3 — Architecture Freeze Note: Foundation Checkpoint

```yaml
Status:             ✅ ARCHITECTURE FREEZE — Foundation Layer
Date:               2026-07-23
Commit:             97504af (Stream 1 — Organization Profile)
Phase:              Wave A → Stream 2 (Rules Catalog)
Stream 1 Tests:     65/65 ✅
Platform Impact:    0 changes ✅
```

──────────────────────────────────────────────────────

## 1. Decisions Made

### 1.1 Compliance Kernel Structure

| Decision | Status | Rationale |
|:---------|:-------|:----------|
| `organization_id` (UUID) as single identity | ✅ Frozen | ADR-005 compliance; all 11 Streams use the same identity |
| `IOrganizationProfileRepository` as sole entry point | ✅ Frozen | Streams 2-11 depend on this port, NOT on SQLAlchemy |
| `OrganizationProfile` = `@dataclass(frozen=True)` | ✅ Frozen | Immutable identity via `replace()`; no `setattr` |
| `version` field for optimistic locking | ✅ Frozen | Monotonic increment, checked in Application Service |
| Transaction ownership in Application Service | ✅ Frozen | Repository does NOT commit; no unit of work leak |
| `compliance.` schema (Product Layer) | ✅ Frozen | Not in `public.` schema; Platform Layer untouched |

### 1.2 Domain Model Boundaries

| Boundary | Status | What it means |
|:---------|:-------|:--------------|
| `OrganizationProfile` ≠ `public.companies` | ✅ Frozen | Legal details (KPP, OGRN, bank, CEO) stay in Platform |
| Compliance Layer ≠ Document Layer | ✅ Frozen | Compliance reads Business Events, NOT PDFs |
| Compliance Layer ≠ Platform Layer | ✅ Frozen | Platform v3.0 frozen; no schema/API changes in `public.*` |
| No `company_id`, `client_id`, `tenant_id` in Compliance | ✅ Frozen | Only `organization_id` |

### 1.3 Audit & Lifecycle Standards

| Standard | Implementation | Scope |
|:---------|:---------------|:------|
| `created_by` / `updated_by` | `str | None` on every domain entity | All Compliance entities (Streams 2-11) |
| `source` | `enum: default / manual / import / law` | Declared in Stream 1, enforced from Stream 2 onward |
| `archived_at` for soft-delete | `datetime | None` | All Compliance entities |
| `version` for optimistic lock | `int`, monotonic | All mutable Compliance entities |
| `Clock` abstraction | `ABC` in `application/interfaces.py` | All Application Services |

### 1.4 Development Conventions

| Convention | Status | Description |
|:-----------|:-------|:------------|
| Clean Architecture layers | ✅ Frozen | `domain/` → `application/` → `infrastructure/` + `api/` |
| Domain has ZERO framework deps | ✅ Frozen | No SQLAlchemy, FastAPI, Pydantic in `domain/` |
| Repository returns domain models | ✅ Frozen | Not ORM rows, not dicts |
| Application Commands (dataclass) | ✅ Frozen | API → Command → Domain, never API schema → Domain directly |
| Tests: 3 levels | ✅ Frozen | unit (domain) + integration (repository) + API (e2e) |

──────────────────────────────────────────────────────

## 2. Immutable Boundaries

### 2.1 What Cannot Be Changed Without ADR

```
┌──────────────────────────────────────────────────────────────┐
│                    FROZEN — ADR REQUIRED                      │
│                                                              │
│  • platform/public.companies structure                       │
│  • platform/accounting.* schema                              │
│  • IOrganizationProfileRepository contract                   │
│  • OrganizationProfile field set                             │
│  • organization_id as PK type                                │
│  • Frozen entity pattern (dataclass + replace)               │
│  • Transaction ownership pattern (Service, not Repository)   │
│  • Clock abstraction                                         │
│  • Clean Architecture layer isolation                        │
│  • Compliance ≠ Document boundary                            │
│  • Compliance ≠ Platform boundary                            │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Contract Stability Rules

1. **Repository Contract is immutable without ADR.**  
   Adding Stream-specific methods to `IOrganizationProfileRepository` requires ADR.  
   If a new query is needed → create a new Application Port, do NOT widen the existing interface.

2. **Domain model fields are frozen without ADR.**  
   Adding/removing/renaming fields on `OrganizationProfile` requires ADR.  
   Streams 2-11 already write code against this shape.

3. **Enum values are extensible but not removable.**  
   New `TaxRegime`, `EntityType`, `ReportingPeriod` values can be added.  
   Existing values cannot be removed or renamed without ADR.

### 2.3 What Is NOT Frozen (Can Evolve Without ADR)

- Implementation details of `SQLAlchemyOrganizationProfileRepository`
- API endpoint format (as long as it doesn't change the domain)
- Test fixtures and test helpers
- `RegionCode` value object (was removed in code — `region_code: str` used directly)
- Error message strings
- Logging and metrics
- Caching layer (as long as it's transparent to consumers)

──────────────────────────────────────────────────────

## 3. Deferred Risks

### 3.1 Risks Carried to Stream 2 (Rules Catalog)

| # | Risk | Severity | Mitigation in Stream 2 |
|:-:|:-----|:---------|:----------------------|
| R1 | `reporting_period` may belong in Rules Catalog, not OrganizationProfile | Medium | Stream 2 must decide: keep in Profile, move to Rule, or both |
| R2 | Rules Reference Resolution — how does Dependency Engine find rules for an org | High | Stream 2 defines `Rules Resolver`: OrganizationProfile → Applicable Rules |
| R3 | Two-level model (Default Rules + Overrides) not yet validated | High | Stream 2 must prove the Git + DB pattern works |
| R4 | Rule evaluation performance at scale | Medium | Stream 2 defines trace structure, performance is Stream 6 |

### 3.2 Risks Carried to Stream 3 (Business Events)

| # | Risk | Severity | Mitigation |
|:-:|:-----|:---------|:-----------|
| R5 | Event schema versioning not stress-tested | Medium | Stream 3 will implement `event_schema_version` and versioned parsers |
| R6 | Append-only log performance | Low | Stream 3 will test with realistic event volumes |

### 3.3 Risks Carried to Stream 4 (Business Facts Engine)

| # | Risk | Severity | Mitigation |
|:-:|:-----|:---------|:-----------|
| R7 | BusinessFactResult computation cost | Medium | Stream 4 will benchmark on-the-fly computation |
| R8 | Cache invalidation strategy | Medium | Stream 4 defines TTL-based + event-driven invalidation |

### 3.4 Risks Carried to Stream 5 (Eligibility Engine)

| # | Risk | Severity | Mitigation |
|:-:|:-----|:---------|:-----------|
| R9 | Eligibility cache correctness | Medium | Stream 5 will implement TTL-based cache with explicit invalidation |

### 3.5 Risks Carried to Stream 6 (Dependency Engine)

| # | Risk | Severity | Mitigation |
|:-:|:-----|:---------|:-----------|
| R10 | Stateless Dependency Engine — can it handle complex requirements? | High | Stream 6 will prove stateless design with real tax scenarios |
| R11 | Explanation quality for unmet requirements | Medium | Stream 6 defines `ExplanationItem` structure |

### 3.6 Risks Carried to Stream 7 (Simulation Engine)

| # | Risk | Severity | Mitigation |
|:-:|:-----|:---------|:-----------|
| R12 | Simulation accuracy vs real outcomes | Medium | Stream 7 will define confidence scoring |

### 3.7 Risks Carried to Stream 11 (Explainability API)

| # | Risk | Severity | Mitigation |
|:-:|:-----|:---------|:-----------|
| R13 | ReasoningGraph × LLM quality | Medium | Stream 11 will define structured graph before LLM rendering |

### 3.8 Cross-Cutting Risks

| # | Risk | Severity | Mitigation |
|:-:|:-----|:---------|:-----------|
| R14 | Multi-tenant isolation (organization_id boundary) not stress-tested | Low | ADR-005 covers principle; Stream 6 will demonstrate |
| R15 | No progress_pct — status-only may frustrate users | Low | Tracked; reconsider if user feedback demands it |
| R16 | Simulation Engine + Compliance Timeline integration complexity | Medium | Stream 8 will define Timeline as pure projection |

──────────────────────────────────────────────────────

## 4. Pending ADRs

### 4.1 ADRs Needed in Stream 2 (Rules Catalog)

| ADR | Title | Description |
|:----|:------|:------------|
| ADR-010 | Two-Level Rules Model | Default Rules (Git) + Organization Overrides (DB) — governance model |
| ADR-011 | Rule Identity & Versioning | Rule → RuleVersion → EffectivePeriod; how rules evolve over time |
| ADR-012 | RequirementExpression AST | ALL/ANY/NOT tree structure; how complex rules compose |
| ADR-013 | DueRule DSL | offset/cron/expression grammar for deadline calculation |
| ADR-014 | Rule Source & Provenance | `source: default | manual | import | law` — who changed what and why |
| ADR-015 | Rules Catalog Validation | Cycle detection, fact reference checks, overlap detection at startup |
| ADR-016 | Rule Evaluation Trace | Trace tree returned with every evaluation; structure for Explainability |

### 4.2 ADRs Needed in Stream 3 (Business Events)

| ADR | Title |
|:----|:------|
| ADR-017 | BusinessEvent taxonomy and hierarchy |
| ADR-018 | Event schema versioning strategy |
| ADR-030 | Append-only event log vs event sourcing |

### 4.3 ADRs Needed in Stream 4 (Business Facts Engine)

| ADR | Title |
|:----|:------|
| ADR-020 | BusinessFactResult computation model (on-the-fly vs cached) |
| ADR-021 | Fact verification priority: event > document > entry |

### 4.4 ADRs Needed in Stream 5 (Eligibility Engine)

| ADR | Title |
|:----|:------|
| ADR-022 | Eligibility cache strategy (TTL + invalidation) |

### 4.5 ADRs Needed in Stream 6 (Dependency Engine)

| ADR | Title |
|:----|:------|
| ADR-023 | Dependency Engine stateless contract |
| ADR-024 | DependencyReport status model (ready/partial/not_ready/blocked) |

### 4.6 ADRs Needed in Stream 7 (Simulation Engine)

| ADR | Title |
|:----|:------|
| ADR-025 | Counterfactual evaluation without AI |

### 4.7 ADRs Needed in Stream 8 (Compliance Timeline)

| ADR | Title |
|:----|:------|
| ADR-026 | Timeline as pure projection of Dependency Reports |

### 4.8 ADRs Needed in Stream 10 (Task Model)

| ADR | Title |
|:----|:------|
| ADR-027 | Task as single model (Calendar + Action Center projections) |
| ADR-028 | Task Provenance (generated_from: report/requirement/simulation/manual) |

### 4.9 ADRs Needed in Stream 11 (Explainability API)

| ADR | Title |
|:----|:------|
| ADR-029 | ReasoningGraph structure + LLM Renderer boundary |

### 4.10 Existing ADRs (Implementation Derived)

| ADR | Title | Status |
|:----|:------|:-------|
| ADR-005 | Multi-tenant organization_id | ✅ Used (Compliance) |
| ADR-007 | Legacy identifier mapping | ⬜ Created after Stream 1 |
| ADR-030 | Append-only event log vs event sourcing | ✅ Draft (Stream 3) |

──────────────────────────────────────────────────────

## 5. Architecture Health Check

### 5.1 Metrics

| Metric | Value | Assessment |
|:-------|:------|:-----------|
| Streams complete | 1 / 11 | 🟢 On track |
| Tests passing | 65 / 65 | 🟢 Solid |
| Platform changes | 0 | 🟢 Zero impact |
| Architecture violations | 0 | 🟢 Clean |
| Deferred risks documented | 16 | 🟢 All tracked |
| Pending ADRs | 24 | 🟢 Planned per stream |
| Backward compatibility | Full | 🟢 No breaking changes |

### 5.2 Strengths

1. **Clean layer separation** — domain has zero framework dependencies
2. **Repository contract** — stable interface for all downstream consumers
3. **Frozen domain pattern** — immutable identity reduces bugs
4. **No platform impact** — `public.companies` and `accounting.*` untouched
5. **Test discipline** — 3-level test pyramid with abstract contract tests
6. **Audit trail** — every entity carries `created_by`, `updated_by`, `source`

### 5.3 Key Watch Items

1. **Stream 2 design quality is critical** — Rules Catalog defines the language for all engines (Streams 4-7). A mistake here propagates.
2. **Two-level model complexity** — Git-based Default Rules + DB-based Overrides must not create sync nightmares.
3. **performance@scale** — Rule evaluation with RequirementExpression AST may be expensive; defer to Stream 6 but design with traceability.
4. **Validation correctness** — Rules Catalog Validation at startup must catch cycles, broken references, and overlapping periods.

### 5.4 Recommended Actions Before Stream 2

- [x] Freeze this checkpoint
- [x] Create ADR-010 (Rule Versioning) during Stream 2 proposal
- [x] Create ADR-011 (Rule Storage — YAML defaults + DB overrides) during Stream 2 proposal
- [x] Create ADR-012 (Override Priority — LAW > MANUAL > IMPORT > DEFAULT) during Stream 2 proposal
- [x] Create ADR-013 (Requirement Expression AST) during Stream 2 proposal
- [x] Create ADR-014 (Rule Evaluation Trace) during Stream 2 proposal
- [x] Create ADR-015 (DueRule Model) during Stream 2 proposal
- [x] Create ADR-016 (RulesResolver Architecture) during Stream 2 proposal
- [ ] Verify `RegionCode` value object status (removed in code, kept in proposal as risk)
- [ ] Run `pytest backend/compliance/tests/ -v` to confirm Stream 1 stability

──────────────────────────────────────────────────────

## Appendix A: Change History

| Date | Stream | Change | ADR |
|:-----|:-------|:-------|:----|
| 2026-07-23 | 1 | Initial foundation freeze | — |

## Appendix B: Quick Reference

```
OrganizationProfile       → Stream 1 ✅      → Frozen
Rules Catalog             → Stream 2 🔵      → In Proposal
Business Events           → Stream 3 🔵      → In Proposal (см. ADR-030)
Business Facts Engine     → Stream 4 ⬜      → Pending
Eligibility Engine        → Stream 5 ⬜      → Pending
Dependency Engine         → Stream 6 ⬜      → Pending
Simulation Engine         → Stream 7 ⬜      → Pending
Compliance Timeline       → Stream 8 ⬜      → Pending
Reporting Workspace       → Stream 9 ⬜      → Pending
Task Model                → Stream 10 ⬜     → Pending
Explainability API        → Stream 11 ⬜     → Pending
```
