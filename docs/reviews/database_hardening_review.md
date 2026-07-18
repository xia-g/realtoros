# Database Hardening Review

**Date:** 2026-06-07
**Scope:** Initial migration (001_initial_schema), 10 SQLAlchemy models, ER Model V1

---

## 1. PostgreSQL Extensions

### Current State

No extensions are enabled in the initial migration.

### Required Extensions

| Extension | Purpose | Required By | Included in Migration? |
|-----------|---------|-------------|----------------------|
| `uuid-ossp` | `gen_random_uuid()` fallback | PostgreSQL < 13 | ❌ Not needed (PG 17 has built-in) |
| `pg_trgm` | Fuzzy string matching (entity resolution) | ADR-0007 | ❌ Missing |
| `vector` | pgvector: embedding storage + ANN search | ADR-0009 | ❌ Missing |

### `uuid-ossp` — Not Required

PostgreSQL 17 has built-in `gen_random_uuid()` — no extension needed. The migration already uses `sa.text("gen_random_uuid()")` correctly. The `uuid-ossp` extension is only needed for PostgreSQL < 13.

### `pg_trgm` — Missing

Required by Stage 2 of entity resolution (fuzzy name matching). Planned for Sprint 1.5 (embedding/resolution migration).

### `vector` — Missing

Required by Stage 3 of entity resolution (pgvector ANN search). Planned for Sprint 1.5 (`003_add_pgvector`).

### Recommendation

- Sprint 1.5 migration `003_add_pgvector` will add: `CREATE EXTENSION IF NOT EXISTS vector`
- Add `pg_trgm` in the same migration: `CREATE EXTENSION IF NOT EXISTS pg_trgm`
- No action needed for `uuid-ossp` (PG 17 native)

---

## 2. Foreign Key Index Analysis

### 2.1 Existing Indexes (in migration)

All FK columns have dedicated indexes in the migration. Full list:

| Table | FK Column | Index Name | Present in Migr. |
|-------|-----------|------------|-----------------|
| users | role_id | `idx_users_role` | ✅ |
| clients | (none) | — | N/A |
| client_contacts | client_id | `idx_client_contacts_client` | ✅ |
| properties | owner_id | `idx_properties_owner` | ✅ |
| deals | property_id | `idx_deals_property` | ✅ |
| deals | created_by | — | ❌ **Missing** |
| deal_participants | deal_id | `idx_deal_participants_deal` | ✅ |
| deal_participants | client_id | `idx_deal_participants_client` | ✅ |
| documents | client_id | `idx_documents_client` | ✅ |
| documents | property_id | `idx_documents_property` | ✅ |
| documents | deal_id | `idx_documents_deal` | ✅ |
| documents | uploaded_by | `idx_documents_uploaded_by` | ✅ |
| communications | client_id | `idx_communications_client` | ✅ |
| communications | deal_id | `idx_communications_deal` | ✅ |
| communications | assigned_to | `idx_communications_assigned` | ✅ |
| communications | created_by | — | ❌ **Missing** |
| tasks | client_id | `idx_tasks_client` | ✅ |
| tasks | deal_id | `idx_tasks_deal` | ✅ |
| tasks | property_id | `idx_tasks_property` | ✅ |
| tasks | assigned_to | `idx_tasks_assigned_status` (composite) | ✅ |
| tasks | created_by | — | ❌ **Missing** |
| tasks | completed_by | — | ❌ **Missing** |

### 2.2 Missing FK Indexes

| Table | FK Column | Risk | Impact |
|-------|-----------|------|--------|
| **deals.created_by** | users.id | Full scan on agent's deals query | Low (deals are per-client, rarely filtered by creator alone) |
| **communications.created_by** | users.id | Full scan on agent's communication history | Medium (agent views own communications daily) |
| **tasks.created_by** | users.id | Full scan on tasks created by user | Low (rarely queried alone; assigned_to is primary) |
| **tasks.completed_by** | users.id | Full scan on completion audit | Low (audit queries are rare) |

**Total missing: 4 FK indexes.** All are on `created_by` or `completed_by` — secondary query paths. The primary query path (`assigned_to`, `property_id`, `deal_id`) has indexes.

These were omitted from the initial migration. They should be added to the next migration (`002_add_leads_and_soft_delete`).

### 2.3 Duplicate Index Risks

| Table | Duplicate Risk | Reason |
|-------|---------------|--------|
| users | `idx_users_phone` + UNIQUE(phone) | UNIQUE creates a b-tree index automatically. `idx_users_phone` is redundant. Same for `email` and `telegram_id`. |
| clients | `idx_clients_phone` + UNIQUE(phone) | Redundant: UNIQUE(phone) already creates an index on `phone`. Same for `telegram_id` (no unique constraint). |

**Total: 2 redundant indexes** (users.phone, users.email — unique constraints already index these). `idx_users_phone` and `idx_users_email` can be removed; the UNIQUE constraint provides the same index.

### 2.4 FK Coverage Summary

| Metric | Count |
|--------|-------|
| Total FK columns | 21 |
| FK indexes in migration | 17 |
| FK indexes missing | 4 (deals.created_by, communications.created_by, tasks.created_by, tasks.completed_by) |
| Redundant FK indexes (duplicate with UNIQUE) | 2 (users.phone, users.email) |
| **Net missing after dedup** | **2** (communications.created_by, tasks.created_by — still needed) |

---

## 3. CHECK Constraints

### 3.1 Existing CHECK Constraints (in migration)

20 CHECK constraints across 7 tables. Complete list:

| Table | Constraint | Values | Status |
|-------|-----------|--------|--------|
| users | `valid_user_status` | active, inactive, blocked | ✅ |
| clients | `valid_client_type` | buyer, seller, tenant, landlord, investor, partner | ✅ |
| clients | `valid_client_status` | lead, active, inactive, archived, blacklisted | ⚠️ Will change (remove 'lead') |
| clients | `valid_client_source` | referral, site, telegram, call, other | ✅ |
| properties | `valid_property_type` | apartment, house, commercial, land, townhouse, penthouse | ✅ |
| properties | `valid_property_status` | available, under_contract, sold, rented, archived, removed | ✅ |
| properties | `valid_deal_type` | sale, rent_short, rent_long, commercial | ✅ |
| properties | `valid_price_currency` | RUB, USD, EUR | ✅ |
| deals | `valid_deal_status` | negotiation, contract_signing, deposit, legal_check, payment, closed, cancelled | ✅ |
| deals | `valid_deal_source` | referral, site, direct, other | ✅ |
| deal_participants | `valid_participant_role` | buyer, seller, tenant, landlord, agent, witness | ✅ |
| documents | `valid_document_type` | contract, passport, extract, deed, receipt, statement, photo, video, report, other | ✅ |
| documents | `valid_document_status` | pending, received, verified, expired, rejected | ✅ |
| communications | `valid_communication_type` | call, email, telegram, whatsapp, meeting, site_message, note | ✅ |
| communications | `valid_direction` | incoming, outgoing | ✅ |
| tasks | `valid_task_status` | pending, in_progress, completed, cancelled | ✅ |
| tasks | `valid_priority` | low, medium, high, critical | ✅ |
| tasks | `valid_task_type` | other, call, email, meeting, inspection, contract, payment | ✅ |

### 3.2 Missing CHECK Constraints

No CHECK constraints are defined as `sa.CheckConstraint()` in the models — all exist only in migration SQL. This is by design (CHECK constraints are DDL-level, not ORM-level in this project's architecture).

However, the following fields lack database-level CHECK constraints and rely solely on application validation:

| Table | Field | Missing CHECK | Risk |
|-------|-------|---------------|------|
| leads | score | `CHECK (score >= 0 AND score <= 1)` | Application could write out-of-range scores |
| leads | budget_min | `CHECK (budget_min >= 0)` | Negative budget values possible |
| leads | budget_max | `CHECK (budget_max >= 0)` | Negative budget values possible |
| properties | area_total | `CHECK (area_total > 0)` | Zero or negative area possible |
| properties | area_living | `CHECK (area_living > 0)` | Zero or negative area possible |
| properties | rooms | `CHECK (rooms > 0)` | Zero rooms possible |
| properties | floor | `CHECK (floor > 0)` | Ground floor = 1, basement should be -1, but 0 is ambiguous |
| deals | price | `CHECK (price > 0)` | Zero or negative deal price possible |
| deals | commission | `CHECK (commission >= 0)` | Negative commission possible |
| deals | commission_percent | `CHECK (commission_percent >= 0 AND commission_percent <= 100)` | Over 100% commission possible |

### 3.3 Numeric Field CHECK Constraints Needed

When the leads table is created (migration 002), add:

```sql
ALTER TABLE leads ADD CONSTRAINT valid_lead_score
    CHECK (score >= 0 AND score <= 1);
ALTER TABLE leads ADD CONSTRAINT valid_lead_budget
    CHECK (budget_min IS NULL OR budget_min >= 0);
ALTER TABLE leads ADD CONSTRAINT valid_lead_budget_range
    CHECK (budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max);
```

For existing tables, consider adding in a future hardening migration:

```sql
ALTER TABLE properties ADD CONSTRAINT valid_area CHECK (area_total IS NULL OR area_total > 0);
ALTER TABLE deals ADD CONSTRAINT valid_deal_price CHECK (price > 0);
ALTER TABLE deals ADD CONSTRAINT valid_commission_pct
    CHECK (commission_percent IS NULL OR (commission_percent >= 0 AND commission_percent <= 100));
```

### 3.4 Score Field CHECK Constraints

| Table | Field | Type | Range | Constraint Exists? |
|-------|-------|------|-------|-------------------|
| leads | score | FLOAT | 0.0 – 1.0 | ❌ (table not yet created) |

### 3.5 Budget Field CHECK Constraints

| Table | Field | Type | Constraint Needed | Exists? |
|-------|-------|------|-------------------|---------|
| leads | budget_min | NUMERIC(15,2) | ≥ 0 | ❌ |
| leads | budget_max | NUMERIC(15,2) | ≥ 0 | ❌ |
| leads | budget_min ≤ budget_max | — | Optional cross-field | ❌ |

---

## 4. ENUM Consistency

### 4.1 No PostgreSQL ENUMs Yet

The current migration uses VARCHAR with CHECK constraints instead of native PostgreSQL ENUM types. This was a deliberate choice in the initial schema (CHECK constraints are easier to modify than ENUMs).

**VARCHAR + CHECK vs Native ENUM:**

| Criterion | VARCHAR + CHECK | Native ENUM |
|-----------|----------------|-------------|
| Storage | ~20 bytes per value | 4 bytes per value |
| Add value | `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT` | `ALTER TYPE ... ADD VALUE` (PG 17: transactional) |
| Remove value | Same as add | Requires ENUM rebuild |
| ORM mapping | Python string | Python enum or string |
| Query plan | Same | Same |

### 4.2 Fields Using CHECK Instead of ENUM

All 20 CHECK constraints (see §3.1) use VARCHAR + CHECK. This is **acceptable** for the current architecture — CHECK constraints are easier to modify during active development. Migration to native ENUMs can be deferred until schema stability.

### 4.3 Python Enum Classes

There are no Python `enum.Enum` classes in the codebase yet. All status/type values are plain strings. This is fine for Sprint 1 — the Pydantic schemas (for API validation) and SQLAlchemy models (for DB storage) both use plain strings. Python enums can be added in a future refactoring sprint.

### 4.4 ADR-0013 ENUMs (Not Yet Created)

ADR-0013 defines 3 new ENUM types that should use **native PostgreSQL ENUMs** (not CHECK constraints):

| ENUM | Values | Recommended Implementation |
|------|--------|---------------------------|
| `lead_source` | telegram, avito, cian, referral, site, call, manual | Native ENUM (stable, unlikely to change) |
| `lead_status` | new, contact_made, qualifying, qualified, converted, lost, spam | Native ENUM (state machine, fixed) |
| `interest_type` | buy, rent_short, rent_long, sell, commercial_buy, commercial_rent, unknown | Native ENUM |

### 4.5 Recommendation

| Approach | Recommended For | Reason |
|----------|----------------|--------|
| VARCHAR + CHECK | Existing 10 tables | Schema still evolving; easier to modify |
| Native ENUM | New tables (leads, lead_events) | Status is a state machine with fixed transitions |
| Python Enum class | Future refactoring | Not needed in Sprint 1; Pydantic validates API input |

---

## 5. UNIQUE Constraints

### 5.1 Current UNIQUE Constraints

| Table | Column(s) | Constraint Name | Type |
|-------|-----------|----------------|------|
| roles | name | UNIQUE(name) | Single column |
| users | phone | UNIQUE(phone) | Single column |
| users | email | UNIQUE(email) | Single column |
| users | telegram_id | UNIQUE(telegram_id) | Single column |
| clients | phone | UNIQUE(phone) | Single column |

### 5.2 UNIQUE Constraints and Soft Delete

When soft delete is implemented (ADR-0010, migration 002), UNIQUE constraints on `phone` and `email` will cause conflicts:

**Problem:**
```sql
-- User deletes client with phone +79161234567
UPDATE clients SET deleted_at = NOW() WHERE phone = '+79161234567';

-- New client with same phone arrives
INSERT INTO clients (phone, ...) VALUES ('+79161234567', ...);
-- ❌ ERROR: duplicate key violates unique constraint "clients_phone_key"
```

**Solution: Partial unique indexes with `WHERE deleted_at IS NULL`:**

```sql
-- Instead of UNIQUE(phone):
CREATE UNIQUE INDEX uq_clients_phone_active
    ON clients(phone) WHERE deleted_at IS NULL;

-- Instead of UNIQUE(email):
CREATE UNIQUE INDEX uq_clients_email_active
    ON clients(email) WHERE deleted_at IS NULL;

-- Same for users:
CREATE UNIQUE INDEX uq_users_phone_active
    ON users(phone) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_email_active
    ON users(email) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_telegram_id_active
    ON users(telegram_id) WHERE deleted_at IS NULL;
```

### 5.3 UNIQUE Constraint Migration Plan

| Table | Current | After Soft Delete | Action |
|-------|---------|------------------|--------|
| roles.name | UNIQUE(name) | Keep as-is (roles never soft-deleted) | None |
| users.phone | UNIQUE(phone) | `uq_users_phone_active WHERE deleted_at IS NULL` | Migration 002 |
| users.email | UNIQUE(email) | `uq_users_email_active WHERE deleted_at IS NULL` | Migration 002 |
| users.telegram_id | UNIQUE(telegram_id) | `uq_users_telegram_id_active WHERE deleted_at IS NULL` | Migration 002 |
| clients.phone | UNIQUE(phone) | `uq_clients_phone_active WHERE deleted_at IS NULL` | Migration 002 |

**Migration SQL pattern:**
```sql
-- Drop old UNIQUE constraint
ALTER TABLE clients DROP CONSTRAINT clients_phone_key;

-- Create partial unique index
CREATE UNIQUE INDEX uq_clients_phone_active
    ON clients(phone) WHERE deleted_at IS NULL;
```

### 5.4 Composite Unique Constraints (Future)

| Table | Columns | When Needed | Reason |
|-------|---------|------------|--------|
| leads | (source, source_id) | ADR-0013 | Prevent duplicate leads from same source |
| deal_participants | (deal_id, client_id, role) | Future | Prevent duplicate roles in same deal |
| documents | file_hash | Future | Prevent duplicate document uploads |

---

## 6. Delete Policy Review

### 6.1 Current `ondelete` Policies by Table

| Table | FK Column | ondelete | Semantics |
|-------|-----------|----------|-----------|
| **users** | role_id | RESTRICT | Cannot delete a role that has users |
| **properties** | owner_id | SET NULL | If client deleted, property becomes ownerless |
| **deals** | property_id | RESTRICT | Cannot delete a property that has deals |
| **deals** | created_by | RESTRICT | Cannot delete a user who created deals |
| **client_contacts** | client_id | CASCADE | Delete contacts when client is deleted |
| **deal_participants** | deal_id | CASCADE | Delete participants when deal is deleted |
| **deal_participants** | client_id | RESTRICT | Cannot delete a client who participates in deals |
| **documents** | client_id | SET NULL | Document remains if client deleted |
| **documents** | property_id | SET NULL | Document remains if property deleted |
| **documents** | deal_id | SET NULL | Document remains if deal deleted |
| **documents** | uploaded_by | RESTRICT | Cannot delete a user who uploaded documents |
| **communications** | client_id | SET NULL | Communication remains if client deleted |
| **communications** | deal_id | SET NULL | Communication remains if deal deleted |
| **communications** | assigned_to | SET NULL | Communication remains if assigned user deleted |
| **communications** | created_by | RESTRICT | Cannot delete a user who created communications |
| **tasks** | client_id | SET NULL | Task remains if client deleted |
| **tasks** | deal_id | SET NULL | Task remains if deal deleted |
| **tasks** | property_id | SET NULL | Task remains if property deleted |
| **tasks** | assigned_to | RESTRICT | Cannot delete user who has assigned tasks |
| **tasks** | created_by | RESTRICT | Cannot delete user who created tasks |
| **tasks** | completed_by | SET NULL | Task remains if completer deleted |

### 6.2 Policy Correctness

| Policy | Count | Assessment |
|--------|-------|------------|
| **RESTRICT** | 9 | Correct — prevents data loss by blocking deletion of referenced records |
| **SET NULL** | 10 | Correct — allows deletion while preserving the dependent record |
| **CASCADE** | 2 | Correct — child data (contacts, participants) has no value without parent |

### 6.3 Interaction with Soft Delete

When soft delete is implemented (ADR-0010), `ondelete` policies interact differently:

```python
# Without soft delete:
DELETE FROM clients WHERE id = '...'
# → triggers ondelete behavior: SET NULL / CASCADE / RESTRICT

# With soft delete:
UPDATE clients SET deleted_at = NOW() WHERE id = '...'
# → ondelete is NOT triggered (it's an UPDATE, not DELETE)
# → RESTRICT policies do NOT block soft delete
# → SET NULL does NOT fire during soft delete
```

This is **correct behaviour**:
- Soft delete preserves referential integrity (FKs still point to the record)
- RESTRICT only blocks actual `DELETE`, not soft delete
- Cascade for `client_contacts` and `deal_participants` should still work on hard delete (cleanup jobs)
- Queries filter `WHERE deleted_at IS NULL` so soft-deleted parents appear deleted

### 6.4 Cascade Risk Audit

| Cascade Path | Risk | Mitigation |
|-------------|------|-----------|
| `clients` ← CASCADE ← `client_contacts` | Low | Contacts are meaningless without client |
| `deals` ← CASCADE ← `deal_participants` | Low | Participants are meaningless without deal |

Both CASCADE paths are correct and low-risk. No accidental cascade can delete important data.

### 6.5 RESTRICT Risk Audit

| RESTRICT Path | Impact | Real-World Scenario |
|--------------|--------|-------------------|
| `roles` ← RESTRICT ← `users` | Cannot delete role with active users | Must reassign users first |
| `properties` ← RESTRICT ← `deals` | Cannot delete property with deals | Must close/cancel deals first |
| `users` ← RESTRICT ← `deals.created_by` | Cannot delete user who created deals | Must reassign deals first |
| `users` ← RESTRICT ← `documents.uploaded_by` | Cannot delete user who uploaded docs | Must reassign documents first |
| `users` ← RESTRICT ← `communications.created_by` | Cannot delete user who wrote comms | Must reassign communications first |
| `users` ← RESTRICT ← `tasks.assigned_to` | Cannot delete user with assigned tasks | Must reassign tasks first |
| `users` ← RESTRICT ← `tasks.created_by` | Cannot delete user who created tasks | Must reassign tasks first |

All RESTRICT policies are correct — they prevent accidental deletion of users who have active responsibilities.

---

## Summary of Findings

| Section | Issue | Severity | Action |
|---------|-------|----------|--------|
| §1 | `pg_trgm` extension missing | Low | Add in migration 003 (Sprint 1.5) |
| §1 | `vector` extension missing | Low | Add in migration 003 (Sprint 1.5) |
| §2.2 | 4 FK indexes missing (deals.created_by, communications.created_by, tasks.created_by, tasks.completed_by) | **Medium** | Add in migration 002 |
| §2.3 | 2 redundant indexes (users.phone, users.email — duplicate with UNIQUE) | Low | Remove in migration 002 |
| §3.2 | 10 numeric fields lack CHECK constraints (price > 0, area > 0, score 0–1) | Low | Deferred: add after schema stabilises |
| §5.2 | 4 UNIQUE constraints conflict with soft delete | **Medium** | Replace with partial unique indexes in migration 002 |
| §6.3 | Soft delete correctly bypasses ondelete RESTRICT | ✅ No action |
| §6.4 | CASCADE policies correct (2 paths, both low-risk) | ✅ No action |
| §6.5 | RESTRICT policies correct (8 paths, all intentional) | ✅ No action |

### Action Items for Migration 002

| # | Action | SQL |
|---|--------|-----|
| 1 | Add missing FK indexes | `CREATE INDEX idx_deals_created_by ON deals(created_by)` (3 more) |
| 2 | Remove redundant indexes | `DROP INDEX idx_users_phone`, `DROP INDEX idx_users_email` |
| 3 | Replace UNIQUE with partial unique indexes | `CREATE UNIQUE INDEX uq_clients_phone_active ON clients(phone) WHERE deleted_at IS NULL` (4 tables) |
| 4 | Add CHECK for leads.score | `ALTER TABLE leads ADD CONSTRAINT valid_lead_score CHECK (score >= 0 AND score <= 1)` |
| 5 | Add CHECK for leads.budget | `ALTER TABLE leads ADD CONSTRAINT valid_lead_budget CHECK (budget_min IS NULL OR budget_min >= 0)` |
