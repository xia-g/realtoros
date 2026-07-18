# Architecture Audit V1

**Date:** 2026-06-07
**Scope:** All domain models, ADRs, architecture documentation, SQLAlchemy models, and migration

---

## Summary

| Category | Verdict |
|----------|---------|
| **Domain consistency** | Good — 10 entities, clear relationships, no duplicates |
| **Database consistency** | Fair — models out of sync with migration on 19 FK ondelete clauses |
| **Relationship correctness** | Good — all 20 back_populates pairs correctly wired |
| **Missing indexes** | None — 50+ indexes defined in migration |
| **Missing constraints** | Fair — models lack ondelete and CHECK constraints |
| **AI requirements** | Good — JSONB, ARRAY, embedding columns, text fields all present |
| **Telegram requirements** | Fair — no Telegram-specific fields (chat_id, message_id) on entities |
| **Document processing** | Good — full 5-layer pipeline documented |
| **Multi-user support** | Fair — role system exists but no row-level security |
| **Auditability** | Fair — timestamps present, but no created_by on all tables |

**Critical issues: 4**
**Important issues: 8**
**Optional improvements: 7**

---

## Critical Issues

### C-1. 19 FK Columns Missing `ondelete` in SQLAlchemy Models

**Severity:** Critical
**Files affected:** `user.py`, `property.py`, `deal.py`, `deal_participant.py`, `document.py`, `communication.py`, `task.py`
**ER V1 spec:** All FK columns specify `ondelete` behavior (RESTRICT / SET NULL / CASCADE)

**Problem:** The Alembic migration (created manually from the ER V1 spec) correctly includes `ondelete` on every FK. But the SQLAlchemy model files omit `ondelete` on 19 out of 21 FK columns. Only `client_contact.client_id` (CASCADE) and `deal_participant.deal_id` (CASCADE) have it.

**Risk:** If someone regenerates migrations from models via `alembic revision --autogenerate`, the generated migration will use PostgreSQL default `NO ACTION` instead of the intended `RESTRICT` / `SET NULL` / `CASCADE`. This is a silent behaviour change — `NO ACTION` defers referential checks and will not cascade deletes.

**Affected FKs:**

| File | FK Column | ER V1 Expects | Model Has |
|------|-----------|---------------|-----------|
| user.py:16 | role_id | `ondelete="RESTRICT"` | missing |
| property.py:29 | owner_id | `ondelete="SET NULL"` | missing |
| deal.py:17 | property_id | `ondelete="RESTRICT"` | missing |
| deal.py:30 | created_by | `ondelete="RESTRICT"` | missing |
| deal_participant.py:14 | client_id | `ondelete="RESTRICT"` | missing |
| document.py:24-27 | client_id, property_id, deal_id, uploaded_by | SET NULL / SET NULL / SET NULL / RESTRICT | all missing |
| communication.py:16-25 | client_id, deal_id, assigned_to, created_by | SET NULL / SET NULL / SET NULL / RESTRICT | all missing |
| task.py:21-28 | client_id, deal_id, property_id, assigned_to, created_by, completed_by | SET NULL / SET NULL / SET NULL / RESTRICT / RESTRICT / SET NULL | all missing |

**Fix:** Add `ondelete=` to every `mapped_column(ForeignKey(...))` call in all affected model files, matching the ER V1 spec.

---

### C-2. Embedding Storage Duplication — No Synchronization Strategy

**Severity:** Critical
**Files affected:** `entity_resolution.md`, `knowledge_graph.md`, `database_schema_v1.md`

**Problem:** Embeddings (vector(384)) are stored in three different places with no documented synchronization:

1. **`clients.embedding` + `clients.name_embedding` + `properties.embedding`** — proposed in `entity_resolution.md`
2. **`entity_embeddings` table** — proposed in `entity_resolution.md` (separate table with model_version, text_hash)
3. **`graph_nodes.embedding`** — proposed in `knowledge_graph.md`

These could hold the SAME embedding for the SAME entity in DIFFERENT tables. When an entity is updated, all three locations must be updated. There is no documented sync strategy, no `ON UPDATE` trigger, no single source of truth.

**Risk:** Entropy — embeddings will diverge over time. Graph queries and resolution queries will return different similarity scores for the same entity pair.

**Recommendation:** Pick ONE storage location for embeddings:
- Option A: Store ON the entity tables (`clients.embedding`, `properties.embedding`) — used by entity resolution. Graph nodes can reference these via JOIN.
- Option B: Store in `entity_embeddings` table — single source of truth. Graph nodes and entity tables both JOIN.
- Option C: Store in `graph_nodes.embedding` — graph is the source of truth. Entity resolution queries graph.

**Recommended: Option A** — embedding is a property of the entity, not of the graph. Graph nodes can JOIN to get embeddings. Drop the separate `entity_embeddings` table and the `graph_nodes.embedding` column.

---

### C-3. `power_of_authority` Typo in Document Classifier LLM Prompt

**Severity:** Critical
**File:** `docs/architecture/document_classifier.md` line 353

**Problem:** The Stage 3 LLM prompt uses `power_of_authority` (typo) as a valid document type. The correct type is `power_of_attorney` as defined in the `LLMClassification` Pydantic schema (line 327) and the `document_subtype` ENUM.

```
# Line 353 (wrong):
- power_of_authority: доверенность на совершение сделок

# Line 327 (correct):
"power_of_attorney",
```

**Risk:** When Stage 3 LLM classifies a power of attorney document, it returns `power_of_authority`. This value will fail ENUM validation (`document_subtype`) and will be rejected or stored as `unknown`. All power of attorney documents will fail auto-classification.

**Fix:** Change `power_of_authority` to `power_of_attorney` in the LLM system prompt.

---

### C-4. `documents_metadata` Table Referenced but Undefined

**Severity:** Critical
**File:** `docs/architecture/entity_extraction.md` line 1063

**Problem:** The integration diagram shows extracted dates, prices, and organizations flowing into a `documents_metadata` table:

```
├──(applied)──► documents_metadata  (dates, prices, organizations)
```

No `documents_metadata` table is defined anywhere — not in `database_schema_v1.md`, not in any architecture doc, not in the migration. The DDL for this table does not exist.

**Risk:** Implementation ambiguity — engineer implementing entity extraction will not know where to store extracted dates/prices/organizations.

**Fix:** Either:
- Define the `documents_metadata` table schema in `database_schema_v1.md`, or
- Remove the reference and store dates/prices/organizations in `extracted_entities.extraction_data` JSONB, or
- Store them in the existing domain tables (`communications` for dates, `deals` for prices, `clients` for organizations).

---

## Important Issues

### I-1. `system_architecture.md` is a Stub

**Severity:** Important
**File:** `docs/architecture/system_architecture.md` (14 lines)

**Problem:** The high-level architecture document shows a flat, three-layer system:

```
Telegram Bot → FastAPI → PostgreSQL
AI Layer: Qwen, DeepSeek, ChatGPT
```

This does not reflect the actual architecture: 10 domain entities, 5-layer document pipeline (OCR → Classifier → Extraction → Resolution → Graph), knowledge graph layer, entity embeddings, Telegram review workflow, and 9 new proposed tables.

**Risk:** New team members reading the architecture doc will have a fundamentally incorrect understanding of the system. Architectural decisions may be made without considering the full complexity.

**Fix:** Rewrite `system_architecture.md` to show:
- Full document pipeline with all 5 layers
- All 10 domain entities and their relationships
- AI model selection by task
- Telegram integration points
- Knowledge graph layer

---

### I-2. `database_schema_v1.md` Missing Embedding Columns

**Severity:** Important
**File:** `docs/domain/database_schema_v1.md`

**Problem:** The ER Model V1 doc defines `clients` and `properties` tables without embedding columns. The entity resolution and knowledge graph docs propose adding `embedding vector(384)` columns to these tables. The schema doc is not synced.

**Fix:** Add `embedding vector(384)` to `clients` and `properties` table definitions in `database_schema_v1.md`. Add the HNSW indexes.

---

### I-3. Trigger Ordering Not Documented

**Severity:** Important
**Files:** `entity_resolution.md`, `knowledge_graph.md`

**Problem:** Both the entity resolution and knowledge graph docs propose triggers on `clients` that fire on `INSERT`:

| Trigger | Before/After | Action | Document |
|---------|-------------|--------|----------|
| `trg_client_embedding` | BEFORE INSERT OR UPDATE | Compute and set embedding | entity_resolution.md |
| `trg_client_graph_node` | AFTER INSERT OR UPDATE | Create graph node | knowledge_graph.md |

These triggers fire on the same table. If they execute in the wrong order, the graph node trigger may not see the embedding (BEFORE trigger runs first and sets the embedding, AFTER trigger creates the graph node — which is the correct order in this case).

However, PostgreSQL does NOT guarantee execution order for triggers on the same table at the same timing level (both AFTER). Using `BEFORE` (embedding) and `AFTER` (graph node) is the correct approach, but this ordering dependency should be explicitly documented.

**Fix:** Add a note to both docs: "The `trg_client_embedding` trigger must fire BEFORE insert; the `trg_client_graph_node` trigger must fire AFTER insert. Embedding must be set before the graph node is created."

---

### I-4. Deal Creation Handoff Ambiguity

**Severity:** Important
**Files:** `entity_extraction.md` (line 1066-1071), `entity_resolution.md` (line 703-706)

**Problem:** The entity extraction document says extracted deal data can be "applied" to create new deal records (`──(applied)──► deals`). The entity resolution document says the deal merge strategy is `no_automerge` — all deal updates require human review.

The ambiguity: are newly created deals (from extraction) also subject to the "no auto-merge" rule? If so, how are they created — must an operator manually confirm every new deal?

**Fix:** Clarify in both docs:
- If no matching deal exists → auto-create (the deal is new, not a merge)
- If a matching deal exists → human review required for any updates
- Add a `"create_strategy": "auto_create"` vs `"merge_strategy": "human_review"` distinction in `DEAL_RESOLUTION_RULES`

---

### I-5. PostgreSQL Version Inconsistency

**Severity:** Important
**Files:** `ADR-0001` (no version), `ADR-0003` (v16), `ADR-0008` (v17)

**Problem:** Three ADRs reference different PostgreSQL versions. The installed version is PostgreSQL 17 (from `pg_lsclusters` output). ADR-0003 says v16 and ADR-0008 says v17.

**Risk:** Features available only in v17 (like `ALTER TYPE ... ADD VALUE` improvements, or HNSW index enhancements in pgvector) may be assumed in later docs but not available if the actual deployment uses v16.

**Fix:** Update ADR-0003 to reflect the actual installed version (v17) and verify pgvector compatibility.

---

### I-6. `pgml` Dependency Inconsistency

**Severity:** Important
**Files:** `entity_resolution.md` (line 437), `knowledge_graph.md` (line 898-900)

**Problem:** Entity resolution doc says "If `pgml` extension is not available, embeddings are computed in Python". The knowledge graph doc uses `pgml.embed()` directly in a SQL trigger without mentioning a Python fallback.

**Risk:** If `pgml` is not installed or fails, the knowledge graph trigger will error silently and embeddings won't be computed.

**Fix:** Either:
- Install `pgml` extension and document it as a required dependency, or
- Remove `pgml` dependency from both docs and compute all embeddings in Python via the `EmbeddingMatcher` class

---

### I-7. No Soft Delete Implementation

**Severity:** Important
**Status:** Deferred in ADR-0003

**Problem:** ER Model V1 defines a soft delete migration path (add `deleted_at TIMESTAMPTZ`), but it is not implemented. Instead, entities use status fields (`archived`, `removed`, `cancelled`) for logical deletion.

**Risk:** No recoverable deletion — once a record's status is changed to `archived`, the original data is not preserved. Accidental deletion of a client or property cannot be undone without a backup.

**Fix:** Implement the soft delete migration:
1. Add `deleted_at TIMESTAMPTZ` to all 10 tables
2. Replace `DELETE` with `UPDATE ... SET deleted_at = NOW()`
3. Add partial indexes: `WHERE deleted_at IS NULL`
4. Update repositories to filter `WHERE deleted_at IS NULL`

---

### I-8. INDEX and CHECK Constraints Not Self-Documented in Models

**Severity:** Important
**Files:** All model files in `backend/models/`

**Problem:** The migration defines 50+ indexes and 20 CHECK constraints. None of these are declared in the SQLAlchemy model files via `__table_args__` or `__mapper_args__`. This means:
- Models are not self-documenting — a developer reading a model cannot see which indexes or constraints apply
- Autogenerate may not detect CHECK constraints (they must be created manually)
- Index changes require altering both the migration and this audit document

**Fix:** Add `__table_args__` with `Index()` and `CheckConstraint()` to each model file. This makes the models self-documenting and ensures autogenerate can detect changes.

---

## Optional Improvements

### O-1. ER Doc ↔ Migration Discrepancies on 3 Fields

**Severity:** Low
**Status:** Models and migration agree; ER doc is wrong

| Field | ER Doc Says | Model + Migration Say | Correct |
|-------|-------------|----------------------|---------|
| `properties.price_per_meter` | NOT NULL | nullable=True | nullable (computed field, can be NULL until calculated) |
| `tasks.task_type` | nullable=YES | nullable=False, default='other' | NOT NULL with default (better for data quality) |
| `tasks.assigned_to` | FK NOT NULL | FK nullable=True | nullable (task can be unassigned) |

**Fix:** Update the ER doc to match the models (which have the correct design).

---

### O-2. No Rejected/Alternative Decisions in ADRs

**Severity:** Low

**Problem:** All 8 ADRs are "Accepted". No ADR records a rejected decision or an alternative that was considered and discarded. This limits the historical record — future developers won't know why certain approaches were rejected.

**Fix:** When creating future ADRs, include a "Rejected Alternatives" section documenting the options that were considered, why they were rejected, and under what conditions they might be revisited.

---

### O-3. `classification_training_log` Undesigned

**Severity:** Low
**File:** `document_classifier.md`

**Problem:** The document classifier doc mentions a `classification_training_log` table for storing training samples but does not provide its DDL. The table is referenced inline but never designed.

**Fix:** Add DDL for `classification_training_log` to the document classifier doc.

---

### O-4. No `created_by` on All Tables

**Severity:** Low
**Current:** Only `deals`, `communications`, `documents`, and `tasks` have `created_by` FK to `users`.

**Problem:** For full auditability, all tables should record who created the record. Currently `clients`, `properties`, `client_contacts`, and `deal_participants` do not track the creating user.

**Fix:** Add `created_by UUID REFERENCES users(id)` to `clients`, `properties`, `client_contacts`, and `deal_participants`. Alternatively, rely on database-level audit logging (pg_audit extension).

---

### O-5. No PostgreSQL `COMMENT ON` for Tables/Columns

**Severity:** Low

**Problem:** The migration creates 10 tables and 100+ columns without any `COMMENT ON` statements. This means `\d+ tablename` in psql shows no descriptions.

**Fix:** Add `COMMENT ON TABLE` and `COMMENT ON COLUMN` statements to the migration. These can be extracted from the domain model documentation.

---

### O-6. No Row-Level Security (RLS) for Multi-Tenant

**Severity:** Low (future)
**Current:** Single agency = single database. Not multi-tenant.

**Problem:** If the system is ever deployed for multiple agencies, there is no row-level security. A user from agency A could, in theory, access agency B's data.

**Fix:** Add `agency_id UUID` to all tables and enable RLS when multi-tenancy is required. Document this as a future expansion path.

---

### O-7. No Full-Text Search Configuration

**Severity:** Low
**Current:** Full-text search is mentioned in the index strategy but not implemented.

**Problem:** The ER Model V1 doc recommends full-text search indexes on `address`, `notes`, and `description` columns. These are not implemented in the migration.

**Fix:** Add `GIN` indexes with `tsvector` configuration for Russian text search:
```sql
ALTER TABLE properties ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('russian', COALESCE(address, ''))) STORED;
CREATE INDEX idx_properties_search ON properties USING GIN (search_vector);
```

---

## Cross-Document Consistency Matrix

| Document | Consistent With | Inconsistent With |
|----------|---------------|-------------------|
| `domain_model.md` | models/*.py | — |
| `database_schema_v1.md` | initial migration | entity_resolution.md, knowledge_graph.md (missing embedding columns) |
| `ocr_layer.md` | — | — |
| `document_classifier.md` | — | ITSELF (power_of_authority typo) |
| `entity_extraction.md` | — | ITSELF (documents_metadata undefined) |
| `entity_resolution.md` | — | knowledge_graph.md (embedding storage), database_schema_v1.md (columns) |
| `knowledge_graph.md` | — | entity_resolution.md (embedding location, trigger ordering) |
| `system_architecture.md` | — | ALL other docs (stub) |

---

## Critical Path — Before Alembic Generation

1. **Fix 19 missing `ondelete` clauses** in models (C-1)
2. **Fix `power_of_authority` → `power_of_attorney`** in LLM prompt (C-3)
3. **Resolve embedding storage** — choose one strategy (C-2)
4. **Define or remove `documents_metadata`** reference (C-4)
5. **Sync `database_schema_v1.md`** with actual column definitions (I-2)
6. **Document trigger ordering** for `clients` table (I-3)
7. **Clarify deal creation vs merge** handoff (I-4)
8. **Fix PostgreSQL version** in ADR-0003 (I-5)
9. **Resolve `pgml` dependency** — install or remove (I-6)

**Safe to proceed with Alembic generation after items 1, 2, and 4 are resolved.** Items 3 and 5-9 can be addressed in parallel.

---

## Related Documentation

- `docs/adr/0001-postgresql.md` — database foundation
- `docs/adr/0002-canonical-domain-model.md` — 10 entity model
- `docs/adr/0003-er-model-v1.md` — schema design (needs version fix)
- `docs/adr/0004-ocr-layer-paddleocr.md` — OCR decision
- `docs/adr/0005-document-classifier.md` — classification strategy
- `docs/adr/0006-entity-extraction.md` — extraction strategy
- `docs/adr/0007-entity-resolution.md` — resolution strategy
- `docs/adr/0008-knowledge-graph.md` — graph adjacency model
- `docs/domain/database_schema_v1.md` — ER model (needs embedding columns)
- `docs/architecture/system_architecture.md` — high-level arch (needs rewrite)
