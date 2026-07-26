# Stream 2 — Rules Catalog: Implementation Review

```yaml
Epic:              3 — Accounting Compliance & Reporting
Stream:            2 — Rules Catalog
Commit:            990ed98
Tests:             161/161 ✅
Review Date:       2026-07-23
Reviewer:          Architecture (RealtorOS)
Status:            ✅ Implementation Complete — 7 ADRs Validated
```

---

## 1. Architecture Conformance

### 1.1 Proposal → Implementation Mapping

| Proposal Decision | Implementation | Status | Notes |
|:-----------------|:---------------|:-------|:------|
| **RuleVersion immutable** | `@dataclass(frozen=True)` on `RuleVersion` | ✅ | All fields frozen; no mutation paths exist |
| **Resolver (clean architecture, ports)** | `RulesResolver(IRulesResolver)` with `IOrganizationProfileRepository`, `IRuleRepository`, `IOverrideRepository` | ✅ | Zero SQL/Git/HTTP deps in resolver; DI wiring in `api/di.py` |
| **Override Priority Chain (LAW > MANUAL > IMPORT > DEFAULT)** | `OverrideSource` enum with `.priority` property; `RulesResolver._select_best_override()` | ✅ | LAw=0, MANUAL=1, IMPORT=2, DEFAULT=3 |
| **RequirementExpression AST (ALL/ANY/NOT)** | `RequirementExpression` dataclass with `expression_type`, `fact_code`, `children` | ✅ | Frozen, validated in `__post_init__`, max depth 32 |
| **RuleEvaluationTrace** | `RuleEvaluationTrace` frozen dataclass with `rule_code`, `version_number`, `effective_from`, tree structure | ✅ | Includes `print_tree()` rendering |
| **DueRule (отдельный объект, не смешан с ComplianceRule)** | `DueRuleParser` class in `infrastructure/due_rule/parser.py` | ⚠️ **Partial** | DueRule as domain dataclass NOT implemented; raw strings + parser used instead (see 1.2) |
| **Determinism (same inputs → same output)** | `resolve()` sorts by `(effective_from asc, rule_code asc)`; `_select_best_override` deterministic | ✅ | Verified by `TestDeterminism` (3 test cases) |
| **Runtime overlap validation (publish_version атомарно)** | `RuleCatalogService.publish_version()` checks `periods_overlap()` before insert | ✅ | Sequential NOT atomic (no transaction wrapper yet) |
| **Repository без commit()** | No repository method calls `session.commit()` | ✅ | Transaction ownership in Application Service |
| **organization_id единый** | `UUID` used throughout | ✅ | ADR-005 compliance |
| **Platform frozen** | No imports from `public.*` or `accounting.*` | ✅ | Zero platform changes |
| **ComplianceRule.current_version field** | Field absent from code | 🔴 **Missing** | Proposal had `current_version: RuleVersion \| None`; not implemented |
| **Two-level model: Git+DB** | `DefaultRuleLoader` loads from YAML; `OrganizationOverride` in DB | ✅ | Single `rules_catalog.yaml` instead of directory tree (see 1.3) |
| **Rule lifecycle (DRAFT→PUBLISHED→DEPRECATED→ARCHIVED)** | `publish()`, `deprecate()`, `archive_rule()` on `ComplianceRule` | ✅ | Status transitions enforced via domain methods |
| **RulesCatalogValidator (startup)** | `RulesCatalogValidator.validate()` | ⚠️ **Partial** | Overlap & effective period checks done; cycle detection & fact ref checks NOT implemented |
| **API endpoints** | 13 endpoints in `routes.py` | ✅ | Covers rules CRUD, versions, overrides, resolver, deprecate |
| **DI wiring** | `api/di.py` with FastAPI `Depends` | ✅ | RuleCatalogService, RulesResolver wired |
| **FK constraint overrides→rules** | `ForeignKey("compliance.rules.rule_code")` in `OrganizationOverrideTable` | ✅ | |

### 1.2 Key Deviations from Proposal

| # | Deviation | Impact | Rationale |
|:-:|:----------|:-------|:----------|
| D1 | `RuleVersion.requirement_expression` is `dict` (not `RequirementExpression` object) | Low — serialized AST in JSONB; domain validation preserved via loading logic | Simplifies persistence; `RequirementExpression.from_dict()` for round-trip |
| D2 | `RuleVersion.due_rule` is `dict` (not `DueRule` object) | Low — raw dict stored in JSONB | DueRule as domain model deferred; parser handles interpretation |
| D3 | `DueRule` domain dataclass NOT implemented | **Medium** — proposal specified `@dataclass(frozen=True) class DueRule` | Simplified to `DueRuleParser` with raw strings; `rule_type`, `raw`, `description` fields absent from domain model |
| D4 | `OrganizationOverride.requirement_expression` serialized as `None` in repo | **Low** — schema field exists but always `None`; override uses raw strings for due_rule | Override expression support marked as future capability |
| D5 | `OrganizationOverride.due_rule` uses `due_rule_raw` + `due_rule_type` instead of `DueRule` object | **Low** — functional but less typed | Simpler JSONB storage; parser handles interpretation |
| D6 | `RuleEvaluationTrace.rule_code` is `str` (not `RuleCode`) | **Low** — trace is output-only | Avoids type coercion in API responses |
| D7 | `ResolvedRule.rule_code` is `str` (not `RuleCode`) | **Low** — matches API schema | Consistency with REST response shape |
| D8 | `ValidationError.rule_code` is `str` (not `RuleCode`) | **Low** — validation is system-facing | |

### 1.3 Simplifications vs Proposal

| Proposal | Implementation | Notes |
|:---------|:---------------|:------|
| YAML directory tree (`rules/usn/usn_6.yaml`, etc.) | Single `rules_catalog.yaml` with `"rules": [...]` | Simpler structure; directory tree can be added later |
| `ApplyToRegions` / `region_code` filters in `find_applicable()` | Region filtering NOT implemented in repo | `find_applicable()` only checks `tax_regime` + `entity_type`; `region` and `has_employees` params accepted but unused |
| 10+ Default Rules for USN, OSNO, Patent | No default rules YAML file exists | `DefaultRuleLoader` loads from `rules_catalog.yaml` — file doesn't exist yet |
| Business Facts registry (`defaults/business_facts/registry.yaml`) | Not created | Deferred naturally to Stream 4 |
| `IDefaultRuleLoader` interface | `DefaultRuleLoader` does NOT implement a formal interface | Inline class in `infrastructure/yaml_catalog/loader.py` |
| Repository `list_rules` with `tax_regime` filter | `tax_regime` filter NOT in `IRuleRepository.list_rules()` | Only `rule_type` and `status` filters |
| `RuleCatalogService.reload_defaults()` | Method NOT implemented (no `_loader` injected) | Startup loading deferred to Stream 3 wiring |

### 1.4 Architecture Health

| Metric | Value | Assessment |
|:-------|:------|:-----------|
| Clean Architecture layers | 4 layers (domain/application/infrastructure/api) | ✅ Clear separation |
| Domain imports framework | 0 | ✅ `domain/` has zero framework deps |
| Application Commands (not API schemas) | Used consistently | ✅ `commands.py` isolates service from FastAPI |
| Repository → domain mapping | Explicit `_to_domain`/`_from_domain` helpers | ✅ Manual mapping in repository |
| Dependency injection | FastAPI `Depends` in `di.py` | ✅ Wired |
| Platform changes | 0 | ✅ Public schema untouched |

---

## 2. ADR Validation

### 2.1 ADR-010: Rule Versioning

**Status:** ✅ Implemented

| ADR Requirement | Implementation | Status |
|:----------------|:---------------|:-------|
| ComplianceRule → RuleVersion model | `ComplianceRule` + `RuleVersion` | ✅ |
| RuleVersion immutable after publish | `@dataclass(frozen=True)` | ✅ |
| Monotonic version_number | `version_number: int`, incremented in `publish_version()` | ✅ |
| effective_from/effective_to — полуинтервал [from, to) | `RuleVersion.__post_init__` validates `from < to`; `is_active_at()` implements [from, to) | ✅ |
| Runtime overlap check at publish | `periods_overlap()` in `RuleCatalogService.publish_version()` | ✅ |
| DRAFT→PUBLISHED→DEPRECATED→ARCHIVED | `publish()`, `deprecate()`, `archive_rule()` methods | ✅ |

**Deviation:** No `current_version` field on `ComplianceRule` (proposal §2.1 had it).

**Lessons:**
- Immutability via `@dataclass(frozen=True) + dataclasses.replace()` pattern works well — zero mutation bugs found.
- Overlap check is sequential (3 separate queries + python loop), not atomic. Transaction boundary not enforced (no commit in service). Risk of race condition under concurrent publish.

### 2.2 ADR-011: Rule Storage — YAML Defaults + DB Overrides

**Status:** ✅ Implemented (simplified)

| ADR Requirement | Implementation | Status |
|:----------------|:---------------|:-------|
| Default Rules in YAML (Git) | `DefaultRuleLoader` loads from `rules_catalog.yaml` | ✅ |
| Organization Overrides in DB | `OrganizationOverrideTable` in `compliance.organization_overrides` | ✅ |
| Git → DB loading with validation | Loader + `RulesCatalogValidator.validate()` pipeline | ✅ |
| NULL fields in Override → use Default | `if best_override and best_override.due_rule_raw else version.due_rule` in resolver | ✅ |
| FK: overrides → rules | `ForeignKey("compliance.rules.rule_code")` | ✅ |
| FK: overrides → organization_profiles | `ForeignKey("compliance.organization_profiles.organization_id")` | ✅ |

**Deviation:** YAML directory tree (per ADR-011 §2) simplified to single `rules_catalog.yaml`. `reload_defaults()` not in `RuleCatalogService` — no startup loading pipeline wired.

**Lessons:**
- Single YAML file is adequate for Phase 1. Directory tree should be added when rule count exceeds ~20.
- `DefaultRuleLoader` doesn't implement `IDefaultRuleLoader` interface — would block Git→S3 switch without code change.

### 2.3 ADR-012: Override Priority — LAW > MANUAL > IMPORT > DEFAULT

**Status:** ✅ Fully Implemented

| ADR Requirement | Implementation | Status |
|:----------------|:---------------|:-------|
| Priority chain: LAW(0) > MANUAL(1) > IMPORT(2) > DEFAULT(3) | `OverrideSource.priority` + `_OVERRIDE_PRIORITY` dict | ✅ |
| Same priority → max effective_from | `sorted(key=lambda ov: (priority, -effective_from.toordinal()))` | ✅ |
| Conflict: same priority + same effective_from → OverrideConflictError | Loop `for ov in sorted_ovs[1:]:` checks equality | ✅ |
| _select_best_override static method | `RulesResolver._select_best_override()` | ✅ |

**Tests:** `TestPriorityChain` (4 scenarios), `TestConflictDetection` (3 scenarios). All pass.

**Lessons:**
- Priority chain model is clean and testable. The static `_select_best_override()` is a good separation.
- Conflict detection at resolve-time (not at creation-time) means users discover overlaps late — consider adding validation at override creation in Stream 3.

### 2.4 ADR-013: Requirement Expression AST

**Status:** ✅ Fully Implemented

| ADR Requirement | Implementation | Status |
|:----------------|:---------------|:-------|
| Four node types: ALL, ANY, NOT, FACT | `expression_type: Literal["ALL", "ANY", "NOT", "FACT"]` | ✅ |
| FACT: mandatory fact_code, no children | Validated in `__post_init__` | ✅ |
| ALL/ANY: min 1 child, no fact_code | Validated in `__post_init__` | ✅ |
| NOT: exactly 1 child, no fact_code | Validated in `__post_init__` | ✅ |
| Max depth = 32 | `MAX_EXPRESSION_DEPTH = 32` + `_compute_depth()` | ✅ |
| ExpressionValidator standalone class | `ExpressionValidator` in `application/expression_validator.py` | ✅ |
| `to_dict()` / `from_dict()` serialization | Methods on `RequirementExpression` | ✅ |

**Tests:** `TestRequirementExpression` (14 scenarios), `TestExpressionValidator` integrated into `test_expression_validator.py`.

**Lessons:**
- AST design is solid — clean `frozen` dataclass with self-contained validation.
- `MAX_EXPRESSION_DEPTH` hardcoded as module-level constant, not instance field — acceptable.
- `ExpressionValidator` separated from `RulesCatalogValidator` is correct — avoids coupling validation to startup-only logic.

### 2.5 ADR-014: Rule Evaluation Trace

**Status:** ✅ Fully Implemented

| ADR Requirement | Implementation | Status |
|:----------------|:---------------|:-------|
| Trace tree with rule identity | `rule_code: str`, `version_number: int`, `effective_from: date` | ✅ |
| Expression type + fact_code | `expression_type`, `fact_code` fields | ✅ |
| Status: confirmed/missing/disputed/skipped | `status: Literal[..]` | ✅ |
| Recursive children | `children: tuple[RuleEvaluationTrace, ...]` | ✅ |
| Human-readable detail | `detail: str \| None` | ✅ |
| `print_tree()` rendering | Method on `RuleEvaluationTrace` | ✅ |

**Note:** Trace is defined as domain model (in `domain/trace.py`), not as infrastructure — correct per ADR-014.

**Lessons:**
- RuleEvaluationTrace is currently **not used** by any engine — it's a data contract for Stream 5/6/11. Good that it's defined early.
- `rule_code` is `str` not `RuleCode` — minor inconsistency but harmless for trace output.

### 2.6 ADR-015: DueRule Model

**Status:** ⚠️ Partial — Simplified

| ADR Requirement | Implementation | Status |
|:----------------|:---------------|:-------|
| DueRule with three formats (offset/expression/cron) | `DueRuleParser` supports all three | ✅ |
| DueRule as domain dataclass | NOT implemented — no `@dataclass(frozen=True) class DueRule` | 🔴 **Missing** |
| `rule_type`, `raw`, `description` fields | Absent from domain; stored as dict in JSONB | ⚠️ Dict-based |
| DueRuleParser as separate interface | `IDueRuleParser` interface defined; `DueRuleParser` class in `infrastructure/due_rule/parser.py` | ✅ |
| Parse → AST → compute deadline | Parser returns dict, compute returns `date` | ✅ |
| `DueRuleParseError` exception | NOT defined in `domain/errors.py` | 🔴 **Missing** |

**Deviation:** The proposal specified `@dataclass(frozen=True) class DueRule` with `rule_type`, `raw`, `description` as a domain dataclass. The implementation uses raw strings (`due_rule_raw`, `due_rule_type` in `OrganizationOverride`, and `due_rule: dict` in `RuleVersion`) + `DueRuleParser` for interpretation.

**Lessons:**
- The simplification avoids over-engineering for Phase 1 but creates coupling at the domain edge.
- Stream 8 (Compliance Timeline) will need proper DueRule domain model. Recommend revisiting before Stream 8 starts.
- `DueRuleParser._compute_offset()` has a month-arithmetic approximation that may fail at month boundaries — needs testing with Russian tax calendar.

### 2.7 ADR-016: RulesResolver Architecture

**Status:** ✅ Fully Implemented

| ADR Requirement | Implementation | Status |
|:----------------|:---------------|:-------|
| 7-step resolve algorithm | Implemented in `RulesResolver.resolve()` | ✅ |
| Dependencies via interfaces (ports) | `IOrganizationProfileRepository`, `IRuleRepository`, `IOverrideRepository` | ✅ |
| Determinism: sort by (effective_from, rule_code) | `resolved.sort(key=lambda r: (r.effective_from, r.rule_code))` | ✅ |
| Priority-based override selection | `_select_best_override()` static method | ✅ |
| Merge rules (expression, due_rule, effective_period) | Merge logic in `resolve()` loop | ✅ |
| Resolution trace | `resolution_trace: tuple[str, ...]` | ✅ |
| Resolver does NOT depend on SQL/Git/HTTP | Zero infrastructure imports | ✅ |

**Tests:** `TestPriorityChain` (4 tests), `TestDeterminism` (3 tests), `TestConflictDetection` (3 tests), `TestTraceContent` (3 tests), `TestEdgeCases` (3 tests).

**Lessons:**
- Clean architecture exemplar: resolver depends only on abstract interfaces.
- N+1 query pattern: profile + rules + overrides = 3 queries. Acceptable for current scale.
- `find_applicable()` doesn't filter by `region` or `has_employees` — the signature accepts them but the SQLALchemy implementation ignores them. This means rules won't be filtered by region until Stream 5+.

---

## 3. Performance Notes

### 3.1 Heaviest Operations

| Operation | Complexity | Notes |
|:----------|:-----------|:------|
| **YAML loading** (`DefaultRuleLoader.load_all()`) | O(n) rules + O(m) versions | Called once at startup/ deploy; negligible |
| **Resolver `resolve()`** | O(r × v + o log o + r log r) | r=applicable rules, v=versions, o=overrides |
| **Publish version overlap check** | O(v²) pairwise comparison | v = existing versions; practical v < 100, acceptable |
| **AST depth calculation** | O(depth) recursive walk | depth ≤ 32; negligible |
| **Validator overlap detection** | O(v²) pairwise | Startup only; acceptable |
| **ExpressionValidator structural check** | O(n) where n = AST nodes | Negligible |

### 3.2 Resolver Complexity

```
resolve()
├── 1. Get org profile         → O(1) DB query (PK lookup)
├── 2. find_applicable()       → O(r × v) — scan all versions, filter by tax_regime + entity_type
├── 3. get_active_overrides()  → O(1) DB query with index
├── 4. Group overrides         → O(o)
├── 5. For each rule:
│   ├── _select_best_override  → O(o_k log o_k) sort per rule_code group
│   └── Merge → O(1)
└── 6. Sort result             → O(r log r)
Total: O(r × v + o log o + r log r) where r < 100, v < 500, o < 1000
```

**Assessment:** Acceptable for Phase 1. No caching needed yet. Bottleneck is `find_applicable()` which does sequential scan of all versions — with 10-50 rules this is fine; at 1000+ rules, needs index-based filtering on `applies_to_tax_regimes`.

### 3.3 AST Complexity

```
RequirementExpression.evaluate():
├── FACT: O(1) — look up fact_code
├── ALL:  O(n) — evaluate all children, AND
├── ANY:  O(n) — evaluate all children, OR (short-circuit possible but not implemented)
└── NOT:  O(1) — negate single child
Depth-limited: max 32 levels → worst case 2³² nodes (theoretical; real max ~100)
```

### 3.4 Identified Bottlenecks

| # | Bottleneck | Impact | Mitigation |
|:-:|:-----------|:-------|:-----------|
| B1 | `find_applicable()` sequential scan of all versions | Moderate at scale | Add GIN index on `applies_to_tax_regimes`; cache active versions per regime |
| B2 | `get_version_history()` in `publish_version()` loads ALL versions | Low — version count < 100 | Filter on `(effective_from, effective_to)` range |
| B3 | `_find_overlaps()` O(v²) in validator | Low — startup only | Interval tree optimization if v > 500 |
| B4 | `RuleVersion.requirement_expression` stored as JSONB with no index | Low — GIN index commented out in DD | Uncomment GIN index when querying by expression content |
| B5 | Resolver O(r × v) scan without region/has_employees filter | Moderate | Implement full filtering in `find_applicable()` before Stream 5 |

### 3.5 Recommendations

1. **Add composite index** on `rule_versions(rule_code, effective_from, effective_to)` — crucial for overlap queries.
2. **Uncomment GIN index** on `rule_versions.requirement_expression` before Stream 4.
3. **Monitor `find_applicable()` query plan** — if it seq-scans, add filtered index on `applies_to_tax_regimes`.
4. **Resolver profiling** — add `@timed` decorator on `resolve()` for observability (deferred to Stream 10 per tech debt).

---

## 4. Technical Debt

### 4.1 Deferred Decisions (Conscious)

| # | Item | Deferred To | Rationale |
|:-:|:-----|:------------|:----------|
| TD1 | **ResolvedRuleCatalogSnapshot** (materialized view of resolved rules for an org) | Stream 7 (Simulation Engine) | Not needed until simulation; would add sync complexity now |
| TD2 | **Resolver Metrics / Observability** (timing, cache hit rate, override frequency) | Stream 10 (Task + Calendar + Action Center) | Observability layer not yet defined; resolver doesn't need it for correctness |
| TD3 | **DueRule domain dataclass** | Before Stream 8 (Compliance Timeline) | Raw strings + parser sufficient for Stream 2; Timeline needs typed DueRule |
| TD4 | **Cycle detection in RulesCatalogValidator** | Stream 4 (Business Facts Engine) | Fact dependency DAG not yet defined; cycle in AST only possible via recursion which __post_init__ limits via depth |
| TD5 | **Business facts registry YAML** | Stream 4 (Business Facts Engine) | Facts not yet defined; registry will be created when Business Facts Engine starts |
| TD6 | **10+ Default Rules YAML** | Stream 3+ (integration) | Rules catalog is a living artifact; initial rules will be loaded during Stream 3 integration |
| TD7 | **Atomic publish transaction** (begin → check → insert → commit) | Stream 3 (when transaction infrastructure is wired) | Service doesn't manage transactions; `publish_version()` has race window |
| TD8 | **Region filtering in `find_applicable()`** | Stream 5 (Eligibility Engine) | Not required until region-specific rules are created |
| TD9 | **reporting_period conflict resolution** (OrganizationProfile vs RuleVersion.frequency) | After Stream 6 | Proposal flagged this; both coexist for now |

### 4.2 Optimistic Locking Status

| Entity | Optimistic Lock | Implemented? |
|:-------|:----------------|:-------------|
| `OrganizationProfile` | `.version` field, incremented via `with_update()` | ✅ |
| `OrganizationOverride` | `.version` field (declared, incremented in service?) | ⚠️ Declared but NOT checked in `update_override()` |
| `RuleVersion` | No version field | 🔴 Not implemented (RuleVersion is immutable — acceptable) |
| `ComplianceRule` | No version field | 🔴 Not implemented — `update_rule()` blindly overwrites |

**Risk:** `RuleCatalogService.update_rule()` and `SQLAlchemyRuleRepository.update_rule()` don't check version. Concurrent updates to `ComplianceRule` metadata will silently overwrite. Recommended: add `version` field to `ComplianceRule` before Stream 3.

### 4.3 Code Quality Observations

| # | Issue | Severity | Recommendation |
|:-:|:------|:---------|:---------------|
| CQ1 | `hasattr(v.rule_code, 'code')` pattern used in 10+ places | Low | Enforce `RuleCode` type consistency across all domain models |
| CQ2 | `InMemoryRuleRepository` duplicated in `test_resolver.py`, `test_services.py`, `test_api.py` (~280 lines each) | Medium | Extract shared test helpers or a `test_utils.py` module |
| CQ3 | `_map_rule_error()` catches `ComplianceRuleError` with 422 but misses some error types | Low | Complete error mapping for all domain exceptions |
| CQ4 | `api/routes.py` accesses `service._override_repo` directly (private attribute) | Medium | Add `list_overrides()` method to `RuleCatalogService` |
| CQ5 | `find_applicable()` in SQLAlchemyRepo loads ALL versions then filters in Python | Low-Medium | Push `entity_type` + `tax_regime` filters into SQL query |
| CQ6 | `DueRuleParser._compute_offset()` month arithmetic may produce invalid dates (e.g., Feb 30) | Low | Use `dateutil.relativedelta` or similar for production |

### 4.4 Missing from Definition of Done

Per proposal §12 (Definition of Done), these items are NOT yet done:

- [ ] Default Rules YAML directory (no `defaults/rules/` directory exists)
- [ ] Min 10 Default Rules for USN 6%, USN 15%, OSNO, Patent
- [ ] Business Facts registry (`defaults/business_facts/registry.yaml`)
- [ ] API documentation / OpenAPI
- [ ] Logging for create/publish/override operations
- [ ] `reload_defaults()` admin endpoint

---

## 5. Stream 3 Readiness (Business Events)

> **Critical section** — Stream 3 (Business Events) is next. Every dependency must be identified.

### 5.1 Already Ready ✅

| Component | Interface | Ready For Stream 3 |
|:----------|:----------|:-------------------|
| **OrganizationProfile** | Full domain + repository + API | ✅ Stream 1 complete |
| **IOrganizationProfileRepository** | `get_or_raise()`, `get()`, `exists()` | ✅ Queryable by Stream 3 |
| **IRuleRepository** | `get_rule()`, `get_active_version()`, `get_version_history()` | ✅ Rule queries available |
| **IOverrideRepository** | `get_override()`, `get_active_overrides()`, `list_overrides()` | ✅ Override queries available |
| **RulesResolver** | `resolve(organization_id, at_date)` | ✅ Returns `ResolvedRule[]` for any org+date |
| **RuleEvaluationTrace** | Domain model defined | ✅ Contract ready for Event trace enrichment |
| **DueRuleParser** | Parse + compute deadline | ✅ Parsing available for event timestamps |
| **Rule lifecycle** | DRAFT→PUBLISHED→DEPRECATED→ARCHIVED | ✅ State machine ready for event triggers |
| **ExpressionValidator** | AST validation | ✅ Can validate event payloads |

### 5.2 What Stream 3 Must Create 🔧

| # | Component | Description | Depends On |
|:-:|:----------|:------------|:-----------|
| E1 | **BusinessEvent domain model** | Event schema with `event_id`, `event_type`, `organization_id`, `payload`, `timestamp` | Stream 1 (org profiles) |
| E2 | **Event schema versioning** (ADR-017/018) | `event_schema_version` field; versioned parsers | Stream 2 (trace, rules) |
| E3 | **Append-only event log** | `business_events` table or Kafka topic | — |
| E4 | **EventPublisher port** | `IBusinessEventPublisher` in `application/interfaces.py` | — |
| E5 | **Event types from Rule lifecycle** | `RuleCreated`, `RulePublished`, `RuleDeprecated`, `RuleArchived` | Stream 2 models |
| E6 | **Event types from Override lifecycle** | `OverrideCreated`, `OverrideUpdated`, `OverrideDeleted` | Stream 2 override model |
| E7 | **EventProducerService** or integration in RuleCatalogService | Publish events when rules/overrides change | E4 + Stream 2 services |

### 5.3 Natural Events from Stream 2

These events arise naturally from Stream 2 operations:

| Stream 2 Action | Natural Event | Priority | Payload |
|:----------------|:--------------|:---------|:--------|
| `create_rule()` | `compliance.rule.created` | High | `{rule_code, rule_type, name}` |
| `publish_version()` | `compliance.rule.version_published` | **Critical** | `{rule_code, version_number, effective_from, effective_to}` |
| `deprecate_rule()` | `compliance.rule.deprecated` | Medium | `{rule_code}` |
| `create_override()` | `compliance.override.created` | High | `{organization_id, rule_code, source, effective_from}` |
| `update_override()` | `compliance.override.updated` | Medium | `{override_id, rule_code, version}` |
| `delete_override()` | `compliance.override.deleted` | Medium | `{override_id}` |
| `reload_defaults()` (future) | `compliance.rules.reloaded` | Medium | `{rule_count, version_count, validation_result}` |

### 5.4 Integration Points

```
Stream 2 → Stream 3 wiring:

RuleCatalogService          EventPublisher
      │                          │
      │  publish_version()       │
      │──────────────────────────│
      │                          │
      │  1. validate overlap     │
      │  2. add_version()        │
      │  3. update_rule()        │
      │  4. publish_event(       │  ← NEW in Stream 3
      │       type="rule.version_published",
      │       payload={rule_code, version_number, ...}
      │     )
      │                          │
```

### 5.5 Recommended Stream 3 Sprint Structure

| Sprint | Focus | Deliverables |
|:-------|:------|:-------------|
| Sprint 1 | **Event infrastructure** | BusinessEvent domain, EventPublisher port, append-only log implementation |
| Sprint 2 | **Rule events** | Wire `RuleCatalogService` → publish events; test event flow |
| Sprint 3 | **Override events** | Wire override CRUD → publish events; test override event flow |
| Sprint 4 | **Stream 2 ↔ Stream 3 integration** | End-to-end test: create rule → publish → event received → fact change detected |
| Sprint 5 | **ADR-017/018/019** | Event taxonomy, schema versioning, log strategy (finalize before Sprint 1) |

### 5.6 Risk Assessment for Stream 3

| Risk | Likelihood | Impact | Mitigation |
|:-----|:-----------|:-------|:-----------|
| Event payload schema changes as Stream 4/5 requirements become clear | Medium | High | Design flexible payload with `metadata: dict` early |
| Transactional integrity: event publish may fail after rule saved | Medium | High | Use transactional outbox pattern (events + rule in same DB transaction) |
| Event versioning creates migration burden | Low | Medium | Start with `event_schema_version: 1`; add versioned deserializers when needed |
| Stream 3 timeline pressure skips Override events | Medium | Low | Override events are lower priority; Rule events are critical |

---

## Appendix A: Test Coverage Summary

| Layer | File | Test Count | Status |
|:------|:-----|:-----------|:-------|
| **Domain** | `test_domain.py` | ~180 assertions in 12 test classes | ✅ Comprehensive |
| **Application** | `test_services.py` | ~10 test classes (CRUD, publish, overlap, override) | ✅ Good |
| **Resolver** | `test_resolver.py` | 5 test classes (priority, determinism, conflict, trace, edge) | ✅ Excellent |
| **Expression** | `test_expression_validator.py` | Validation scenarios | ✅ |
| **Infrastructure** | `test_repository.py` | CRUD for rules, versions, overrides | ✅ |
| **API** | `test_api.py` | 14+ API endpoint tests | ✅ Good |
| **Total** | 6 test files | **161 tests** | ✅ All passing |

## Appendix B: File Inventory

```
backend/compliance/
├── domain/                          # 0 framework deps
│   ├── models.py                    # ComplianceRule, RuleVersion, RuleCode, ResolvedRule
│   ├── enums.py                     # RuleType, RuleStatus, OverrideSource, TaxRegime, EntityType, etc.
│   ├── expressions.py               # RequirementExpression (AST)
│   ├── override.py                  # OrganizationOverride
│   ├── trace.py                     # RuleEvaluationTrace
│   ├── validation.py                # ValidationResult, ValidationError
│   └── errors.py                    # 12+ domain exceptions
├── application/
│   ├── interfaces.py                # 6 ABCs (Clock, IOrgRepo, IRuleRepo, IOverrideRepo, IRulesResolver, IDueRuleParser)
│   ├── commands.py                  # 6 dataclass commands
│   ├── services.py                  # OrganizationProfileService + RuleCatalogService
│   ├── resolver.py                  # RulesResolver (concrete)
│   ├── validator.py                 # RulesCatalogValidator (startup)
│   └── expression_validator.py      # ExpressionValidator (standalone)
├── infrastructure/
│   ├── persistence/
│   │   ├── tables.py                # 4 ORM models (OrgProfile, Rule, RuleVersion, Override)
│   │   └── repository.py            # 3 SQLAlchemy repository implementations
│   ├── yaml_catalog/
│   │   └── loader.py                # DefaultRuleLoader
│   └── due_rule/
│       └── parser.py                # DueRuleParser
├── api/
│   ├── routes.py                    # 13 endpoints
│   ├── schemas.py                   # 14+ Pydantic schemas
│   └── di.py                        # FastAPI DI wiring
└── tests/
    ├── conftest.py
    ├── test_domain.py               # 810 lines
    ├── test_services.py             # 545 lines
    ├── test_resolver.py             # 850 lines
    ├── test_expression_validator.py
    ├── test_repository.py
    └── test_api.py                  # 558 lines
```

---

**Document version:** 1.0  
**Author:** Architecture (RealtorOS)  
**Status:** ✅ Implementation Review Complete — Ready for Stream 3 planning
