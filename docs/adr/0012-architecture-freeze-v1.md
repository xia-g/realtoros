|# ADR-0012|

Date: 2026-06-07|

## Context

The Real Estate OS architecture has reached a stable baseline. All core design work is complete:

- 10 domain entities with full bidirectional relationships
- ER Model V1 with PostgreSQL 17 schema, UUID PKs, audit fields, CHECK constraints, 50+ indexes
- 5-layer document processing pipeline (OCR → Classifier → Extraction → Resolution → Knowledge Graph)
- Knowledge Agent V1 orchestrator connecting all pipeline stages
- 11 previous ADRs documenting every architectural decision

Further architectural changes must follow a formal process to prevent undocumented drift, regression, and inconsistency.

## Decision: Architecture Freeze V1

The following architecture documents and decisions are **frozen** effective immediately. No changes may be made to them without a new ADR.

### Frozen Artifacts

| Layer | Document | Version |
|-------|----------|---------|
| **Domain Model** | `docs/domain/domain_model.md` | Canonical — 10 entities |
| | `docs/domain/client.md` | Client entity |
| | `docs/domain/property.md` | Property entity |
| | `docs/domain/deal.md` | Deal entity |
| | `docs/domain/document.md` | Document entity |
| | `docs/domain/communication.md` | Communication entity |
| | `docs/domain/task.md` | Task entity |
| | `docs/domain/user.md` | User entity |
| **ER Model** | `docs/domain/database_schema_v1.md` | ER Model V1 |
| | `docs/domain/entities.md` | PostgreSQL DDL |
| | `backend/migrations/versions/001_initial_schema.py` | Initial migration |
| | All 10 model files in `backend/models/` | SQLAlchemy 2 models |
| **Knowledge Graph** | `docs/architecture/knowledge_graph.md` | Adjacency list on PostgreSQL |
| | `docs/adr/0008-knowledge-graph.md` | Graph ADR |
| | `docs/adr/0009-embedding-storage-and-metadata.md` | Embedding strategy |
| **Knowledge Agent** | `docs/architecture/knowledge_agent_v1.md` | Pipeline orchestrator |
| | `docs/adr/0011-knowledge-agent-v1.md` | Agent ADR |
| **Supporting Architecture** | `docs/architecture/ocr_layer.md` | PaddleOCR + Tesseract |
| | `docs/architecture/document_classifier.md` | 3-stage classification |
| | `docs/architecture/entity_extraction.md` | 2-stage extraction |
| | `docs/architecture/entity_resolution.md` | 4-stage resolution |

### Not Frozen (open for implementation-level changes)

| Area | Reason |
|------|--------|
| `docs/architecture/audit_v1.md` | Contains issues to be resolved, not frozen architecture |
| `docs/architecture/system_architecture.md` | Identified as a stub in audit; needs rewrite |
| `docs/domain/migrations.md` | Operational guide, not architectural |
| `docs/project_status.md` | Active status tracker, updated per task |
| `docs/development_rules.md` | Operational rules, not architectural |
| `docs/backlog.json` | Task tracking, not architectural |
| Implementation code | Code follows frozen architecture; optimizations within frozen boundaries permitted |
| Test code | Tests verify frozen architecture |

## Change Procedure

Any modification to a frozen artifact requires:

### Step 1: ADR Proposal

Create a new ADR document at `docs/adr/ADR-NNNN-title.md` containing:

```
|# ADR-NNNN|

Date: YYYY-MM-DD|

## Context

Why the change is needed. What problem does it solve?
What alternatives were considered?

## Proposal

Specific, concrete description of the change.
References to frozen documents + specific sections/lines.

## Impact

- Documents affected: list of files
- Models affected: list of model files
- Migration required: yes/no + migration name
- ADRs superseded: none / list of ADR numbers
- Re-implementation required: what existing code must change

## Risk Assessment

- Breaking change: yes/no
- Data migration required: yes/no
- Rollback plan: how to revert if the change causes issues

## Status

Proposed
```

### Step 2: Technical Review

The proposer must demonstrate:
1. All frozen documents affected are explicitly listed
2. No undiscovered side effects on non-affected documents
3. Migration path (forward + rollback) is defined
4. Consistency with all 11 previous ADRs is checked

### Step 3: Approval

The ADR status moves through:

```
Proposed → Under Review → Accepted | Rejected
                         → Accepted with Modifications
```

### Step 4: Implementation

Once Accepted:
1. Update ALL affected frozen documents atomically
2. Generate Alembic migration if schema changes
3. Update `project_status.md` to reflect the change
4. The ADR number is added to the list in this document's "Superseded By" section

### Step 5: Documentation

- The new ADR's number and title are added to this document
- Any superseded ADRs are noted in the new ADR's "Impact" section
- `project_status.md` is updated

## Exemptions

The following do NOT require a new ADR:

| Change | Reason |
|--------|--------|
| Bug fixes in implementation code | Code must match frozen architecture; bugs are implementation errors |
| Performance optimizations | Must not change data models or API contracts |
| Additional indexes | Query optimization, not schema change |
| Additional CHECK constraints | Data quality, not structural |
| Implementation of pipeline stages | Code fills in frozen architecture; architecture is the blueprint |
| Additional MCP tools | Tool additions are additive, not architectural |
| Additional LLM prompts | Prompt engineering, not architecture |

## Superseded By

_(to be filled when future ADRs modify frozen artifacts)_

| ADR | Date | Change |
|-----|------|--------|
| — | — | — |

## Reason

- **Prevents architectural drift** without a formal decision record
- **Ensures consistency** — any schema change is checked against all 11 existing ADRs
- **Provides rollback safety** — every change has a documented migration path
- **Limits scope creep** — exemptions allow implementation flexibility without freezing progress
- **Clear accountability** — each change has an ADR author, review, and approval

## Status

Accepted
