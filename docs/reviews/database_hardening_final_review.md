# Database Layer — Final Architectural Decision Review

**Date:** 2026-06-07
**Scope:** All database layer decisions before T2 implementation. This review freezes the database architecture.

---

## PART 1 — Status / ENUM Strategy

### Options Analysis

| Criterion | Option A: VARCHAR + CHECK | Option B: Mixed (proposal) | Option C: Native ENUM everywhere |
|-----------|--------------------------|---------------------------|----------------------------------|
| **Migration complexity** | None (current state) | Low (add ENUMs for new tables) | Medium (alter 20 existing CHECK → ENUM) |
| **Operational risk** | None | Low | Medium (ENUM values cannot be removed without table rewrite) |
| **Storage per value** | ~20 bytes (VARCHAR) | 4 bytes (ENUM) for new, 20 for old | 4 bytes everywhere |
| **Add value** | `DROP CONSTRAINT + ADD CONSTRAINT` | Easy for ENUMs (`ALTER TYPE ADD VALUE`) | Same for all |
| **Remove value** | `DROP CONSTRAINT + ADD CONSTRAINT` | Hard for ENUMs (`ALTER TYPE` requires rebuild) | Hard for all |
| **Active development** | Schema changes weekly — CHECK is easier to modify | Best of both | Premature optimisation |
| **ORM mapping** | Python string | Python string or enum | Python string or enum |
| **Query performance** | Identical | Identical | Identical |

### Recommendation: Option B — Mixed Approach

**Decision:**

| Table Type | Strategy | Rationale |
|-----------|----------|-----------|
| **Existing 10 tables** | VARCHAR + CHECK (keep as-is) | Schema still evolving. CHECK constraints are trivial to modify during active development. |
| **New `leads` table** | Native PostgreSQL ENUM for `status` | Lead status is a fixed state machine (ADR-0013). 7 values, well-defined transitions, unlikely to change. |
| **New `lead_events`** | VARCHAR (no constraint on `event_type`) | Event types will grow as new features are added. VARCHAR + application validation is more flexible. |
| **New `audit_log`** | Native PostgreSQL ENUM for `event_type` + `entity_type` | 28 event types and 16 entity types are comprehensive and stable. Future additions via `ALTER TYPE ... ADD VALUE` (PG 17 makes this transactional). |

### Migration Plan

```
Migration 002:
  leads.status          → CREATE TYPE lead_status AS ENUM (...)       (NEW)
  clients.status        → Keep VARCHAR + CHECK (remove 'lead' value)  (ALTER CHECK)
  All other statuses    → Keep VARCHAR + CHECK                        (no change)

Migration 003 (future, when needed for audit_log):
  audit_log.event_type  → CREATE TYPE audit_event_type AS ENUM (...)  (NEW)
  audit_log.entity_type → CREATE TYPE audit_entity_type AS ENUM (...) (NEW)
```

### ADR-0014: Status Field Strategy

A formal ADR is not required for this decision — it is a **database implementation strategy**, not an architectural change. The domain model is unaffected (entities still have `status: str` in Python regardless of whether the DB uses VARCHAR + CHECK or ENUM). The architecture freeze (ADR-0012) covers domain model and ER model structure — the implementation detail of CHECK vs ENUM is beneath the freeze threshold.

**Status:** This decision is documented here and does not require a separate ADR.

---

## PART 2 — Soft Delete + Unique Indexes

### Business Identifier Review

#### Users

| Field | Type | Current | After Soft Delete | Recommendation |
|-------|------|---------|-------------------|---------------|
| `email` | VARCHAR(255) | UNIQUE | `CREATE UNIQUE INDEX uq_users_email_active ON users(email) WHERE deleted_at IS NULL` | **Partial unique index** — email must be unique among active users. Deleted users' emails can be reused. |
| `phone` | VARCHAR(20) | UNIQUE | `CREATE UNIQUE INDEX uq_users_phone_active ON users(phone) WHERE deleted_at IS NULL` | **Partial unique index** — same reasoning as email. |
| `telegram_id` | VARCHAR(100) | UNIQUE | `CREATE UNIQUE INDEX uq_users_telegram_id_active ON users(telegram_id) WHERE deleted_at IS NULL` | **Partial unique index** — telegram_id is unique among active users. |

#### Clients

| Field | Type | Current | After Soft Delete | Recommendation |
|-------|------|---------|-------------------|---------------|
| `phone` | VARCHAR(20) | UNIQUE | `CREATE UNIQUE INDEX uq_clients_phone_active ON clients(phone) WHERE deleted_at IS NULL` | **Partial unique index** — critical for dedup. A deleted client's phone must be reusable. |

#### Leads

| Field | Type | Current | After Soft Delete | Recommendation |
|-------|------|---------|-------------------|---------------|
| `(source, source_id)` | ENUM + VARCHAR | Not created yet | `CREATE UNIQUE INDEX uq_leads_source ON leads(source, source_id) WHERE deleted_at IS NULL` | **Partial unique index** — prevents duplicate leads from the same external source. Must allow re-import after lead is deleted. |
| `phone` | VARCHAR(20) | Not created yet | No unique constraint | **No uniqueness** — same person can have multiple leads from different sources. Dedup happens during lead→client conversion. |

#### Documents

| Field | Type | Current | After Soft Delete | Recommendation |
|-------|------|---------|-------------------|---------------|
| `file_hash` | VARCHAR(64) | No constraint | `CREATE UNIQUE INDEX uq_documents_hash ON documents(file_hash)` | **UNIQUE (not partial)** — SHA-256 hash must be globally unique. Even deleted documents should prevent re-upload of the same file. If re-upload is needed, use a new document version. |
| `external_id` | VARCHAR(255) | No constraint | No unique constraint | **No uniqueness** — not all documents have external IDs. When integrations are added, use `(source, external_id)` composite. |

### Final DDL Recommendations

```sql
-- Migration 002 actions for UNIQUE constraints:

-- 1. Users — drop UNIQUE, create partial unique indexes
ALTER TABLE users DROP CONSTRAINT users_phone_key;
ALTER TABLE users DROP CONSTRAINT users_email_key;
ALTER TABLE users DROP CONSTRAINT users_telegram_id_key;
DROP INDEX IF EXISTS idx_users_phone;     -- redundant with old UNIQUE
DROP INDEX IF EXISTS idx_users_email;     -- redundant with old UNIQUE

CREATE UNIQUE INDEX uq_users_phone_active ON users(phone) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_email_active ON users(email) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_telegram_id_active ON users(telegram_id) WHERE deleted_at IS NULL;

-- 2. Clients — drop UNIQUE, create partial unique index
ALTER TABLE clients DROP CONSTRAINT clients_phone_key;
DROP INDEX IF EXISTS idx_clients_phone;   -- redundant with old UNIQUE

CREATE UNIQUE INDEX uq_clients_phone_active ON clients(phone) WHERE deleted_at IS NULL;

-- 3. Leads — create partial unique index (new table, no migration needed)
CREATE UNIQUE INDEX uq_leads_source ON leads(source, source_id) WHERE deleted_at IS NULL;

-- 4. Documents — create unique index on hash (not partial — global uniqueness)
CREATE UNIQUE INDEX uq_documents_hash ON documents(file_hash);
```

### Keep as UNIQUE (not partial)

| Table | Field | Reason |
|-------|-------|--------|
| `roles` | `name` | Roles are never soft-deleted |
| `documents` | `file_hash` | Hash must be globally unique, even for deleted docs |

---

## PART 3 — Foreign Key Index Audit

### Current State

21 FK columns across 8 tables. 17 have indexes in the migration. 4 are missing.

### Missing FK Indexes

| Table | FK Column | Missing Since | Query Pattern | Priority |
|-------|-----------|---------------|---------------|----------|
| `deals` | `created_by` | Migration 001 | "Find deals created by agent X" | **Low** — this query is rare. The `property_id` and `participants` paths are the primary deal access patterns. |
| `communications` | `created_by` | Migration 001 | "Find communications created by agent X" | **Medium** — agents view their own communication history. The `assigned_to` + `client_id` paths cover most use cases. |
| `tasks` | `created_by` | Migration 001 | "Find tasks created by agent X" | **Low** — the `assigned_to` + `status` composite index covers the primary access pattern. |
| `tasks` | `completed_by` | Migration 001 | "Audit trail: who completed what" | **Low** — audit queries are rare and not latency-sensitive. |

### Duplicate Indexes (Redundant)

| Index | Duplicates With | Action | Reason |
|-------|----------------|--------|--------|
| `idx_users_phone` | UNIQUE(phone) index | **Remove** | UNIQUE already creates a b-tree index |
| `idx_users_email` | UNIQUE(email) index | **Remove** | Same |
| `idx_users_telegram_id` | UNIQUE(telegram_id) index | **Remove** | Same (will be replaced by partial unique index) |
| `idx_clients_phone` | UNIQUE(phone) index | **Remove** | Same (will be replaced by partial unique index) |

### Final FK Indexing Policy

```sql
-- Migration 002 actions for FK indexes:

-- REMOVE (redundant with UNIQUE, will be replaced by partial unique indexes)
DROP INDEX IF EXISTS idx_users_phone;
DROP INDEX IF EXISTS idx_users_email;
DROP INDEX IF EXISTS idx_users_telegram_id;
DROP INDEX IF EXISTS idx_clients_phone;

-- ADD (missing FK indexes)
CREATE INDEX idx_deals_created_by ON deals(created_by);
CREATE INDEX idx_communications_created_by ON communications(created_by);
CREATE INDEX idx_tasks_created_by ON tasks(created_by);
CREATE INDEX idx_tasks_completed_by ON tasks(completed_by);
```

### FK Index Decision Rationale

Even though `created_by` queries are rare, the cost of a missing index when they DO happen is a full sequential scan of the entire table. At 100K+ records, this becomes a multi-second query. The index overhead (a few MB) is negligible. **Add all 4.**

---

## PART 4 — PostgreSQL Extensions

### Evaluation

| Extension | Purpose | Required By | Size | Risk |
|-----------|---------|-------------|------|------|
| `pg_trgm` | Fuzzy string matching (entity resolution stage 2) | ADR-0007 | Negligible | None |
| `vector` | pgvector: embedding storage + ANN search | ADR-0009, ADR-0008 | ~5 MB | None |
| `pg_stat_statements` | Query performance monitoring | Operations | Negligible | None |

### Decision

| Extension | Migration | Justification |
|-----------|-----------|---------------|
| `pg_trgm` | **Migration 002** | Entity resolution is a Sprint 2 dependency. If migration 002 is the last DB change before Sprint 2, pg_trgm must be available. Adding it to 002 is zero risk and prevents a blocker. |
| `vector` | **Migration 003** | pgvector is only needed when the embedding service runs (Sprint 1.5). Adding it in 002 would create an unused extension. Migration 003 is the natural home alongside the embedding columns. |
| `pg_stat_statements` | **Manual (DBA)** | This is an operational tool, not a schema dependency. DBAs enable it via `postgresql.conf`. No migration needed. |

### Migration 002 SQL

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

No other extensions in migration 002.

---

## PART 5 — Full Text Search Strategy

### Search Requirements

| Entity | Search Fields | Query Pattern | Latency Requirement |
|--------|---------------|---------------|-------------------|
| Client | full_name, phone, notes | Partial name match, exact phone, keyword search in notes | < 200 ms |
| Property | address, description, notes | Address lookup, keyword in description | < 200 ms |
| Document | title, extracted text (via OCR) | Title search, full-text in OCR content | < 500 ms |
| Lead | full_name, phone, notes | Same pattern as Client | < 200 ms |

### Technology Comparison

| Technology | Use Case | Coverage | Complexity |
|-----------|----------|----------|------------|
| `pg_trgm` GIN index | Fuzzy string matching: names, addresses, partial text | All entities | Low — single index per column |
| `GIN tsvector` | Full-text search with linguistic processing (stemming, ranking) | Description, OCR text, notes | Medium — requires tsvector column + trigger |
| `ILIKE` + B-tree | Exact/prefix search on phone numbers | Phone (exact match) | None — already supported |
| Hybrid (trgm + tsvector) | Best of both: fuzzy name + full-text content | Full search across all fields | Medium |

### Recommendation: Hybrid Approach

| Search Type | Technology | Index | Applies To |
|------------|-----------|-------|------------|
| **Name/identity search** | `pg_trgm` GIN | `GIN (column gin_trgm_ops)` | clients.full_name, leads.full_name, users.full_name |
| **Phone search** | B-tree | Existing `idx_clients_phone` (partial unique) | clients.phone, leads.phone |
| **Address search** | `pg_trgm` GIN | `GIN (address gin_trgm_ops)` | properties.address |
| **Full-text content** | `GIN tsvector` | `GIN (search_vector)` with generated column | properties.description, documents.title, clients.notes, leads.notes |
| **Exact hash lookup** | B-tree | `uq_documents_hash` | documents.file_hash |

### Implementation Decision

**Postpone full-text search to Sprint 3.** For Sprint 1 and Sprint 2:

1. **Name search** uses `ILIKE` with existing B-tree indexes (acceptable for < 10K records)
2. **Phone search** uses exact match on existing indexes (already sufficient)
3. **Address search** uses `ILIKE` on existing `idx_properties_created_at` B-tree (acceptable for MVP)

**Add pg_trgm in migration 002** (per Part 4) but do NOT create GIN indexes yet. The trgm indexes should be created when the search feature is implemented (Sprint 3), not before — unused indexes waste write performance.

**Final decision:** `pg_trgm` extension installed, but GIN indexes created lazily with search feature implementation.

---

## PART 6 — Audit Scale Review

### Table Projections

| Table | Events/Document | Est. Daily Volume | Est. Annual Volume |
|-------|----------------|-------------------|-------------------|
| `audit_log` | ~10 per operation | 1,000–2,000 | 365K–730K |
| `lead_events` | ~5 per lead | 100–500 | 36K–182K |
| `pipeline_events` | ~10 per document | 50–200 (at 20 docs/day) | 18K–73K |

### Index Strategy for Scale

| Table | Critical Indexes | Supporting Indexes |
|-------|-----------------|-------------------|
| `audit_log` | `(created_at DESC)` — time-based queries | `(entity_type, entity_id)` — entity lookup |
| | `(correlation_id)` — operation grouping | `(user_id)` — user activity |
| | `(tenant_id, created_at DESC)` — multi-tenant | `(event_type, created_at DESC)` — event analytics |
| `lead_events` | `(lead_id)` — lead history | `(event_type)` — pipeline analysis |
| `pipeline_events` | `(document_id)` — per-doc timeline | `(stage)` — stage performance |

### Partitioning Thresholds

| Volume | Storage | Partitioning Needed? | Strategy |
|--------|---------|---------------------|----------|
| 100K events | ~50 MB | **No** | Single table, indexes sufficient |
| 1M events | ~500 MB | **No** | Single table, index maintenance recommended (REINDEX monthly) |
| 10M events | ~5 GB | **Yes** | **Partition by month** — `PARTITION BY RANGE (created_at)` |
| 100M events | ~50 GB | **Yes** | Partition by month + archive to cold storage for > 2 years |

### When Partitioning Becomes Necessary

```sql
-- Migration to add when audit_log exceeds 5M rows (~2.5 GB)
-- Estimated: 18 months after launch at 1,500 events/day

-- Step 1: Convert to partitioned table
CREATE TABLE audit_log_new (
    LIKE audit_log INCLUDING DEFAULTS INCLUDING CONSTRAINTS
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_log_2026_q4 PARTITION OF audit_log_new
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');
CREATE TABLE audit_log_2027_q1 PARTITION OF audit_log_new
    FOR VALUES FROM ('2027-01-01') TO ('2027-04-01');
-- ... repeat for each quarter

-- Step 2: Attach existing data
ALTER TABLE audit_log_new ATTACH PARTITION audit_log_2026_q3
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');

-- Step 3: Swap tables
DROP TABLE audit_log CASCADE;
ALTER TABLE audit_log_new RENAME TO audit_log;
```

### Retention Strategy

| Table | Hot (full indexes) | Warm (online, limited indexes) | Cold (archive) |
|-------|-------------------|-------------------------------|----------------|
| `audit_log` | 90 days | 1 year (drop GIN index on metadata) | 3 years → CSV export |
| `lead_events` | 90 days | 1 year | 3 years |
| `pipeline_events` | 30 days | 90 days | 1 year |

**Decision:** No partitioning for MVP. Monitor row count quarterly. Plan partitioning when `audit_log` exceeds 5M rows (estimated 12–18 months post-launch).

---

## PART 7 — pgvector Readiness

### Requirements

| Use Case | When | Priority | Vector Dimension |
|----------|------|----------|-----------------|
| Entity resolution (clients) | Sprint 2 | **Critical** | 384 (multilingual-e5-small) |
| Entity resolution (properties) | Sprint 2 | **Critical** | 384 |
| Similar document search | Sprint 3 | Medium | 384 |
| Similar client discovery | Sprint 3 | Low | 384 |
| Lead dedup (future) | Future | Low | 384 |

### Decision: Keep pgvector in Migration 003 (Sprint 1.5)

**Rationale:**
1. Migration 002 is already large (soft delete + leads + lead_events + index changes + constraints). Adding vector columns would make it harder to review and rollback.
2. pgvector is not needed until the embedding service runs. The first Sprint that requires embeddings is Sprint 1.5 (AI Foundation), where the `EmbeddingService` class is implemented.
3. Migration 002 is focused on data model changes (soft delete, leads, audit). Vector columns are a separate concern (AI infrastructure).
4. If pgvector is needed earlier, it can be added via a quick hotfix migration — `CREATE EXTENSION vector; ALTER TABLE clients ADD COLUMN embedding vector(384);` — this is a 5-minute operation with no data migration.

### If pgvector Were in Migration 002

| Pro | Con |
|-----|-----|
| One less migration to track | Migration 002 scope expands beyond "data model" |
| Embedding columns exist from day 1 | Unused columns in DB for weeks |
| — | Larger rollback surface |

**Final: Migration 003.** Not migration 002.

---

## PART 8 — Final Go/No-Go

### Critical Blockers

| # | Blocker | Affects | Resolution |
|---|---------|---------|------------|
| 1 | UNIQUE constraints on phone/email/telegram_id will conflict with soft delete | users, clients | Replace with partial unique indexes `WHERE deleted_at IS NULL` (Part 2) |
| 2 | `clients.status` CHECK constraint includes `'lead'` which must be removed per ADR-0013 | clients | Alter CHECK: remove `'lead'`, add `'lead_conversion'` to `source` (ADR-0013) |
| 3 | 4 missing FK indexes | deals, communications, tasks | Add in migration 002 (Part 3) |
| 4 | 4 redundant indexes cause unnecessary write overhead | users, clients | Remove in migration 002 (Part 3) |

### Recommended Changes (in Migration 002)

```sql
-- === 1. EXTENSIONS ===
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- === 2. SOFT DELETE — Add deleted_at to all 10 tables ===
ALTER TABLE roles ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ;
-- ... (all 10 tables)

-- === 3. UNIQUE → PARTIAL UNIQUE INDEXES ===
ALTER TABLE users DROP CONSTRAINT users_phone_key;
ALTER TABLE users DROP CONSTRAINT users_email_key;
ALTER TABLE users DROP CONSTRAINT users_telegram_id_key;
ALTER TABLE clients DROP CONSTRAINT clients_phone_key;

CREATE UNIQUE INDEX uq_users_phone_active ON users(phone) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_email_active ON users(email) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_telegram_id_active ON users(telegram_id) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_clients_phone_active ON clients(phone) WHERE deleted_at IS NULL;

-- === 4. REMOVE REDUNDANT INDEXES ===
DROP INDEX IF EXISTS idx_users_phone;
DROP INDEX IF EXISTS idx_users_email;
DROP INDEX IF EXISTS idx_users_telegram_id;
DROP INDEX IF EXISTS idx_clients_phone;

-- === 5. ADD MISSING FK INDEXES ===
CREATE INDEX idx_deals_created_by ON deals(created_by);
CREATE INDEX idx_communications_created_by ON communications(created_by);
CREATE INDEX idx_tasks_created_by ON tasks(created_by);
CREATE INDEX idx_tasks_completed_by ON tasks(completed_by);

-- === 6. UPDATE CLIENTS CHECK CONSTRAINT (ADR-0013) ===
ALTER TABLE clients DROP CONSTRAINT valid_client_status;
ALTER TABLE clients ADD CONSTRAINT valid_client_status
    CHECK (status IN ('active', 'inactive', 'archived', 'blacklisted'));
ALTER TABLE clients DROP CONSTRAINT valid_client_source;
ALTER TABLE clients ADD CONSTRAINT valid_client_source
    CHECK (source IN ('referral', 'site', 'telegram', 'call', 'other', 'lead_conversion'));

-- === 7. CREATE LEADS + LEAD_EVENTS TABLES (per ADR-0013) ===
-- (full DDL from ADR-0013)
-- Includes: leads with native ENUM for status + lead_source + interest_type
-- Includes: lead_events table
-- Includes: leads checks for score (0-1), budget (>=0, min <= max)
-- Includes: uq_leads_source partial unique index
-- Includes: all ADR-0013 indexes

-- === 8. ADD created_by TO 4 TABLES (ADR-0010) ===
ALTER TABLE clients ADD COLUMN created_by UUID REFERENCES users(id);
ALTER TABLE properties ADD COLUMN created_by UUID REFERENCES users(id);
ALTER TABLE client_contacts ADD COLUMN created_by UUID REFERENCES users(id);
ALTER TABLE deal_participants ADD COLUMN created_by UUID REFERENCES users(id);

-- === 9. ADD COMMENT ON (ADR-0010) ===
COMMENT ON TABLE clients IS 'Клиенты агентства — физические и юридические лица';
-- ... (one per table + key columns)

-- === 10. PARTIAL INDEXES FOR SOFT DELETE ===
CREATE INDEX idx_roles_active ON roles(deleted_at) WHERE deleted_at IS NULL;
-- ... (one per table)
```

### Optional Improvements (Deferred)

| # | Improvement | Defer To | Reason |
|---|-------------|----------|--------|
| 1 | pgvector extension + embedding columns | Migration 003 | Not needed until Sprint 1.5 |
| 2 | Full-text search GIN indexes | Sprint 3 | Not needed until search feature |
| 3 | `audit_log` partitioning | > 5M rows | Not needed for MVP |
| 4 | Python ENUM classes for status fields | Future refactoring | Not needed — Pydantic validates API |
| 5 | Additional CHECK constraints (price > 0, area > 0) | Future hardening | Low risk — application validates |
| 6 | `pg_stat_statements` extension | DBA setup | Operational tool, not a schema dependency |

### Final Verdict

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              DATABASE LAYER: GO ✅                          ║
║                                                           ║
║  Migration 002 scope:                                      ║
║    • pg_trgm extension                                     ║
║    • Soft delete (deleted_at on 10 tables)                 ║
║    • Partial unique indexes (4 → WHERE deleted_at IS NULL) ║
║    • Remove 4 redundant indexes                            ║
║    • Add 4 missing FK indexes                              ║
║    • Update clients CHECK constraints (ADR-0013)           ║
║    • Create leads + lead_events tables (ADR-0013)          ║
║    • Add created_by to 4 tables (ADR-0010)                 ║
║    • Add COMMENT ON (ADR-0010)                             ║
║    • Partial indexes for soft delete                       ║
║                                                           ║
║  Migration 003 (Sprint 1.5):                              ║
║    • pgvector extension + embedding columns                ║
║                                                           ║
║  After this review:                                        ║
║    Database architecture is FROZEN.                        ║
║    Any future schema changes require ADR approval          ║
║    per Architecture Freeze V1 (ADR-0012).                  ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
```

---

## Decision Log

| Decision | Choice | Documented In |
|----------|--------|---------------|
| Status field strategy | Option B — Mixed (VARCHAR+CHECK for existing, native ENUM for leads, VARCHAR for lead_events, native ENUM for audit_log event/entity types) | Part 1 |
| Soft delete unique indexes | Partial unique indexes `WHERE deleted_at IS NULL` for all business identifiers except roles.name and documents.file_hash | Part 2 |
| FK index policy | Add all 4 missing indexes. Remove 4 redundant indexes. | Part 3 |
| pg_trgm extension | Migration 002 (no GIN indexes yet — create lazily with search feature) | Part 4 |
| vector extension | Migration 003 (Sprint 1.5) | Part 4, Part 7 |
| pg_stat_statements | Manual DBA setup | Part 4 |
| Full-text search | Hybrid (pg_trgm for names/addresses, tsvector for content). Defer index creation to Sprint 3. | Part 5 |
| Audit partitioning | Not needed until > 5M rows (~18 months post-launch) | Part 6 |
| pgvector in migration 002 | **No** — keep in migration 003 | Part 7 |
| **T2 Implementation** | **GO** — all 4 critical blockers have resolutions | Part 8 |

---

## Related Documentation

- `docs/reviews/database_hardening_review.md` — Technical analysis preceding this decision
- `docs/adr/0010-soft-delete-and-audit.md` — Soft delete + audit foundation
- `docs/adr/0013-lead-management-model.md` — Lead entity + lead_events
- `docs/adr/0012-architecture-freeze-v1.md` — Change procedure for frozen architecture
- `docs/architecture/backend_bootstrap.md` — Repository soft-delete pattern
- `docs/architecture/audit_log.md` — Audit log table design
- `docs/domain/database_schema_v1.md` — ER Model V1
- `docs/sprints/sprint_01.md` — Sprint 1 task breakdown
