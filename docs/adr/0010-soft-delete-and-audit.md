|# ADR-0010|

Date: 2026-06-07|

## Context

Architecture audit V1 identified that the system has no soft delete capability. ER Model V1 (ADR-0003) defined a migration path (add `deleted_at TIMESTAMPTZ` to all tables) but deferred implementation. Currently, entities use status fields (`archived`, `removed`, `cancelled`) for logical deletion, which is not recoverable.

Additionally, `created_by` is missing on 4 tables (`clients`, `properties`, `client_contacts`, `deal_participants`), limiting auditability.

## Decision

### 1. Soft Delete — Add `deleted_at` to All 10 Tables

```sql
ALTER TABLE roles ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE clients ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE client_contacts ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE properties ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE deals ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE deal_participants ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE documents ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE communications ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE tasks ADD COLUMN deleted_at TIMESTAMPTZ;
```

**Partial indexes** (more efficient than `WHERE deleted_at IS NULL`):
```sql
CREATE INDEX idx_roles_active ON roles(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_active ON users(deleted_at) WHERE deleted_at IS NULL;
-- ... same pattern for all 10 tables
```

**Repository layer change:**
- `list()` and `get()` methods append `WHERE deleted_at IS NULL` automatically
- `delete()` method performs `UPDATE SET deleted_at = NOW()` instead of `DELETE`
- Hard delete is available as `delete_hard()` for TTL-based cleanup jobs

**Status field interaction:**
- Setting `status = 'archived'` does NOT set `deleted_at`
- Setting `deleted_at` overrides status — a deleted record is always hidden
- Archived records are visible but marked; deleted records are hidden

### 2. Add `created_by` to 4 Tables

```sql
ALTER TABLE clients ADD COLUMN created_by UUID REFERENCES users(id);
ALTER TABLE properties ADD COLUMN created_by UUID REFERENCES users(id);
ALTER TABLE client_contacts ADD COLUMN created_by UUID REFERENCES users(id);
ALTER TABLE deal_participants ADD COLUMN created_by UUID REFERENCES users(id);
```

These are nullable to support legacy data. New records must set `created_by`.

### 3. Add `COMMENT ON` for All Tables

```sql
COMMENT ON TABLE clients IS 'Клиенты агентства — физические и юридические лица';
COMMENT ON COLUMN clients.full_name IS 'ФИО или наименование организации';
-- ... one comment per table and column, sourced from domain model docs
```

## Reason

- **Recoverable deletion:** `deleted_at` enables point-in-time recovery and undo. Status-only deletion is irreversible.
- **Partial indexes:** `WHERE deleted_at IS NULL` on active records improves query performance for all list/get operations.
- **Minimal migration risk:** Adding nullable columns is a backward-compatible change. No data migration required.
- **Audit completeness:** `created_by` on all tables enables full audit trail. Currently 6 of 10 tables have it.
- **Self-documenting schema:** `COMMENT ON` enables `\d+` inspection without reading separate docs.

## Status

Accepted
