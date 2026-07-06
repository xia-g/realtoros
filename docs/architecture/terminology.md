# RealtorOS Terminology

**Complete glossary for the Knowledge Access Platform.**

## A

| Term | Definition |
|------|-----------|
| **Agreement** | Business interpretation of one or more documents (SALE, LEASE, SERVICE, etc.). NOT a Document entity. |
| **AgreementParticipant** | Entity with a role in an Agreement (SELLER, BUYER, LANDLORD, etc.). Not a list[str] — includes role, share, valid_from, valid_to. |
| **AgreementResolver** | Service that orchestrates SemanticInterpreter + AgreementMatcher → Agreement. |
| **AgreementMatcher** | Finds existing Agreements by number, document references, date, parties. |
| **Alias** | Alternative representation of a canonical entity (different name, abbreviation, typo). |
| **Authority** | How much the platform trusts a source document type. Configurable: VERY_LOW to OFFICIAL. |
| **AuthorityResolver** | Resolves authority level for a document role. | 

## B

| Term | Definition |
|------|-----------|
| **BuildPlan** | Declarative description of which Projections to build and in what order. No executable code. |
| **Builder** | Specialized service that reads Domain and returns a Projection. EntityProjectionBuilder, AgreementProjectionBuilder, etc. |
| **BusinessContext** | Aggregated result of analysis: entities + relationships + agreements + properties + candidate deals. |
| **BusinessEntity** | Canonical business entity (Person, Company, Property, Document, Bank, Government). |
| **BusinessFact** | Immutable observation extracted from a document. Describes what was found, not what it means. |

## C

| Term | Definition |
|------|-----------|
| **CanonicalEntity** | Single representation of a business entity after identity resolution. Different names/INNs → one entity. |
| **CanonicalProperty** | Single representation of a property (cadastre, address, area). |
| **CanonicalAgreement** | Single representation of an agreement after resolution. |
| **ChangeTracker** | Service that creates immutable KnowledgeRevisions, computes deltas, builds timelines. |
| **Conflict** | When two sources disagree about the same fact (area, owner, address). Both values preserved. |
| **CQRS** | Command Query Responsibility Segregation. Write → Domain events. Read → Projections. |

## D

| Term | Definition |
|------|-----------|
| **Delta** | Difference between two KnowledgeRevisions. Non-destructive. |
| **Determinism** | Same input + same revision → identical output. Applies to Projections, Queries, and ExecutionPlans. |
| **DocumentRevision** | Version of a document (OCR improved, user corrected). Facts reference a specific revision, not just document_id. |
| **Domain** | Source of truth. Entities, Facts, Graph, Revisions. No infrastructure dependencies. |

## E

| Term | Definition |
|------|-----------|
| **EdgeType** | Types of edges in KnowledgeGraph: MENTIONS, REFERS_TO, PARTICIPATES_IN, SUPPORTS, RESULTED_IN, OWNS, RELATES_TO, ATTACHED_TO. |
| **EntityIdentifier** | How we find an entity: INN, OGRN, CADASTRE, EMAIL, PHONE, BANK_ACCOUNT, BIK, ADDRESS, CONTRACT_NUMBER. |
| **EntityExtractor** | Extracts BusinessEntities from OCR result. Neutral — no business interpretation. |
| **EntityResolver** | Deduplicates entities by (identifier_type, normalized_value). |
| **ExecutionPlan** | Technology-independent internal computation model. Not SQL, not Cypher. |
| **Explainability** | Every result can explain itself: which predicates matched, which facts supported, what authority. |

## F

| Term | Definition |
|------|-----------|
| **FactType** | Types of neutral facts: DOCUMENT_HAS_PARTY, DOCUMENT_HAS_PROPERTY, DOCUMENT_HAS_AMOUNT, DOCUMENT_HAS_DATE, etc. |
| **FactExtractor** | Extracts neutral observation facts. NO business inference. |

## G

| Term | Definition |
|------|-----------|
| **GraphBuilder** | Single entry point for KnowledgeGraph construction. All edges validated against GraphSchema. |
| **GraphNodeType** | ENTITY, PROPERTY, DOCUMENT, AGREEMENT, DEAL, RELATIONSHIP, FACT. |
| **GraphPath** | Explainable path between two nodes with weight, confidence, hop_count. |
| **GraphSchema** | Validation rules for allowed edge connections. |
| **GraphVersion** | Monotonic version of KnowledgeGraph. |

## I

| Term | Definition |
|------|-----------|
| **IdentityResolver** | Normalizes identifiers → matches existing → merges aliases → creates CanonicalEntity. |
| **Immutable** | Object state never changes after creation. All Facts, Revisions, Queries, Projections are immutable. |
| **Intent Document** | Serializable, transportable description of what the user wants to find (KnowledgeQuery). |
| **Invariant** | Architectural rule that must never be violated. 35 across the platform. |

## K

| Term | Definition |
|------|-----------|
| **KnowledgeAccessPlatform** | v2.1 epoch. Transforms domain knowledge into queryable, explainable projections. |
| **KnowledgeConflict** | Records disagreement between two sources. OPEN → RESOLVED / IGNORED. |
| **KnowledgeDelta** | Difference between two KnowledgeRevisions. |
| **KnowledgeGraph** | Domain-level graph abstraction. NOT Neo4j. NOT a DB. 14 traversal methods. |
| **KnowledgePlatform** | v2.0 epoch. Facts → Identity → Agreements → Graph → Revisions. |
| **KnowledgeQuery** | Declarative query. Describes WHAT to find, never HOW. Immutable, serializable. |
| **KnowledgeQueryEngine** | Computes ExecutionPlan from KnowledgeQuery. Planner + Optimizer + Resolver + Assembler. |
| **KnowledgeRevision** | Immutable snapshot of knowledge at a point in time. Monotonic, append-only. |
| **KnowledgeState** | Description of current knowledge (counts, trust summary). Not a graph. |
| **KnowledgeVersion** | Version tracking for rebuildable projections. |

## M

| Term | Definition |
|------|-----------|
| **MasterDataContext** | Result of identity resolution: canonical entities, properties, agreements, merge candidates. |
| **MergeCandidate** | Pair of entities that may be the same (score ≥ 95 → review, ≥ 99 → auto-merge). |
| **Materialized Projection** | Pre-built read model for fast query access. Fully rebuildable from Domain. |

## N

| Term | Definition |
|------|-----------|
| **NormalizationService** | Normalizes company names, addresses, phones, emails, cadastres to canonical form. |

## O

| Term | Definition |
|------|-----------|
| **OperationalStore** | Source of truth: events, entities, agreements, graph. Never merged with Projection. |

## P

| Term | Definition |
|------|-----------|
| **PathExplanation** | Explainable path detail: summary, evidence, confidence. |
| **Predicate** | Universal query filter. Domain-agnostic core: `Predicate(type, params)`. Extensions via PredicateRegistry. |
| **PredicateRegistry** | Maps predicate_type → semantics (subject types, required params, backend hint). |
| **Projection** | Immutable read model. Never source of truth. Fully rebuildable. |
| **ProjectionCoordinator** | Decides WHAT to rebuild (stale check → plan → refresh). |
| **ProjectionId** | Identity of a projection: `Entity:780527855675`, `Property:78:10:1`. |
| **ProjectionQueryService** | Read-only access to projections. |
| **ProjectionRefreshService** | Executes BuildPlan. No decision-making. |
| **ProjectionStore** | Replace-only persistence. No merge, no patch. |
| **ProjectionVersion** | (knowledge_revision, schema_version) — nothing else. |
| **Provenance** | Where a fact came from: document_id, page, OCR fragment, extractor_version. |

## Q

| Term | Definition |
|------|-----------|
| **QueryComposition** | AND, OR, NOT, EXISTS, IN, ALL/ANY. |
| **QueryContext** | Runtime enrichment: user, permissions, workspace, locale. Optional. |
| **QueryEngine** | See KnowledgeQueryEngine. |
| **QueryExplanation** | Why a result was included/excluded: reasons, facts, confidence. |
| **QueryValidationReport** | Validates query before execution: errors, warnings, complexity. |
| **QueryScope** | Search boundaries: revision, document_ids, time_range, workspace. |

## R

| Term | Definition |
|------|-----------|
| **Rebuildable** | A projection can be deleted and rebuilt without data loss. All projections are rebuildable. |
| **Replace-only** | Store contract: no merge, no patch, only full replacement. |
| **ResultAssembler** | Merges multiple projection results into single KnowledgeResult. |
| **ReturnShape** | Declarative description of result form: PROJECTION, SUMMARY, COUNT, TIMELINE. |

## S

| Term | Definition |
|------|-----------|
| **SemanticInterpreter** | Converts neutral facts → business semantics (SELLER, BUYER, LANDLORD). |
| **Snapshot** | Serializable representation of KnowledgeGraph for audit/replay. |
| **StalenessPolicy** | Pure function: `is_stale(projection, latest_revision) → bool`. |
| **StrategySelector** | Chooses execution strategy: SEQUENTIAL, PARALLEL, GRAPH_FIRST, HYBRID. |

## T

| Term | Definition |
|------|-----------|
| **Timeline** | Chronological history for an entity: revisions, changes, confidence evolution. |
| **TraversalOptions** | Parameters for graph traversal: max_depth, allowed types, minimum weight. |
| **TrustLevel** | How much the platform trusts a fact: UNKNOWN → LOW → MEDIUM → HIGH → VERIFIED. |
| **TrustScore** | Accumulates confidence from supporting documents. Never decreases automatically. |

## W

| Term | Definition |
|------|-----------|
| **WorkspaceGraph** | Subgraph of KnowledgeGraph. E.g.: one deal + one property + one counterparty. |
