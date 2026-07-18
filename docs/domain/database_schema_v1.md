# Real Estate OS — ER Model V1

## Overview

Database schema version 1 based on the canonical domain model. Designed for PostgreSQL 16 with UUID primary keys, soft delete support, audit fields, and future AI integration.

## Design Principles

1. **UUID Primary Keys** — Distributed-friendly, sortable, no collisions
2. **Soft Delete** — `deleted_at` nullable timestamp for recoverable deletion
3. **Audit Fields** — `created_at`, `updated_at`, `deleted_at` on all tables
4. **AI Support** — JSONB fields for flexible AI metadata, embeddings, vector search
5. **Foreign Key Constraints** — Enforce referential integrity
6. **Index Strategy** — Composite indexes for common query patterns, partial indexes for soft deletes

---

## Table List

| Table | Purpose | Soft Delete | Audit Fields |
|-------|---------|-------------|--------------|
| `roles` | System roles with permissions | No | Yes |
| `users` | System users (agents, managers, support) | No | Yes |
| `clients` | Individual or legal entity clients | No | Yes |
| `client_contacts` | Additional contacts for legal entities | No | Yes |
| `properties` | Real estate assets | No | Yes |
| `deals` | Transaction records | No | Yes |
| `deal_participants` | Client roles in deals | No | Yes |
| `documents` | Files and documents | No | Yes |
| `communications` | Interaction records | No | Yes |
| `tasks` | Action items | No | Yes |

---

## Table Definitions

### 1. roles

**Purpose:** System role definitions with permissions.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `name` | VARCHAR(50) | NO | - | Role name (admin, agent, manager, support) |
| `permissions` | JSONB | NO | '[]' | Array of permission codes |
| `description` | TEXT | YES | NULL | Role description |
| `is_system` | BOOLEAN | NO | FALSE | System role (cannot be deleted) |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `name` UNIQUE
- `is_system` NOT NULL

**Indexes:**
- `idx_roles_name` — B-tree on `name` (unique)
- `idx_roles_is_system` — B-tree on `is_system`

**Soft Delete:** No (system table, permanent delete)

**Future AI Support:**
- `permissions` JSONB can store permission patterns for AI-based access control analysis
- `description` TEXT can store role summaries for LLM-based role explanations

---

### 2. users

**Purpose:** System users (agents, managers, support staff).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `role_id` | UUID | NO | - | FK to roles.id |
| `status` | VARCHAR(20) | NO | 'active' | User status (active, inactive, blocked) |
| `full_name` | VARCHAR(255) | NO | - | User full name |
| `phone` | VARCHAR(20) | YES | NULL | Phone number (unique) |
| `email` | VARCHAR(255) | YES | NULL | Email address (unique) |
| `telegram_id` | VARCHAR(100) | YES | NULL | Telegram user ID (unique) |
| `telegram_username` | VARCHAR(100) | YES | NULL | Telegram username |
| `telegram_chat_id` | VARCHAR(100) | YES | NULL | Telegram chat ID |
| `password_hash` | VARCHAR(255) | NO | - | Password hash (bcrypt) |
| `avatar` | VARCHAR(500) | YES | NULL | Avatar image URL |
| `settings` | JSONB | NO | '{}' | User preferences (JSON) |
| `last_login` | TIMESTAMPTZ | YES | NULL | Last login timestamp |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `status` CHECK (status IN ('active', 'inactive', 'blocked'))
- `phone` UNIQUE
- `email` UNIQUE
- `telegram_id` UNIQUE

**Foreign Keys:**
- `role_id` → `roles(id)` ON DELETE RESTRICT

**Indexes:**
- `idx_users_role` — B-tree on `role_id`
- `idx_users_status` — B-tree on `status`
- `idx_users_telegram_id` — B-tree on `telegram_id`
- `idx_users_phone` — B-tree on `phone`
- `idx_users_email` — B-tree on `email`
- `idx_users_created_at` — B-tree on `created_at` (for recent users)

**Soft Delete:** No (users cannot be soft deleted, only blocked)

**Future AI Support:**
- `settings` JSONB can store AI model preferences, tone settings
- `last_login` for AI-based user activity analysis
- `avatar` URL can be analyzed by vision AI for user verification

---

### 3. clients

**Purpose:** Individual or legal entity clients.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `type` | VARCHAR(20) | NO | 'buyer' | Client type (buyer, seller, tenant, landlord, investor, partner) |
| `status` | VARCHAR(20) | NO | 'lead' | Client status (lead, active, inactive, archived, blacklisted) |
| `full_name` | VARCHAR(255) | NO | - | Client full name |
| `phone` | VARCHAR(20) | YES | NULL | Phone number (unique) |
| `email` | VARCHAR(255) | YES | NULL | Email address |
| `telegram_id` | VARCHAR(100) | YES | NULL | Telegram user ID (unique) |
| `telegram_username` | VARCHAR(100) | YES | NULL | Telegram username |
| `source` | VARCHAR(50) | NO | 'other' | Lead source (referral, site, telegram, call, other) |
| `notes` | TEXT | YES | NULL | Client notes |
| `tags` | TEXT[] | NO | '{}' | Client tags (for filtering) |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `type` CHECK (type IN ('buyer', 'seller', 'tenant', 'landlord', 'investor', 'partner'))
- `status` CHECK (status IN ('lead', 'active', 'inactive', 'archived', 'blacklisted'))
- `source` CHECK (source IN ('referral', 'site', 'telegram', 'call', 'other'))

**Indexes:**
- `idx_clients_type_status` — B-tree on `type`, `status`
- `idx_clients_source` — B-tree on `source`
- `idx_clients_telegram_id` — B-tree on `telegram_id`
- `idx_clients_phone` — B-tree on `phone`
- `idx_clients_created_at` — B-tree on `created_at`

**Soft Delete:** No (clients cannot be soft deleted, only archived/blacklisted)

**Future AI Support:**
- `tags` TEXT[] can store AI-generated tags for lead scoring
- `source` for AI-based lead source analysis
- `notes` TEXT for AI-powered sentiment analysis

---

### 4. client_contacts

**Purpose:** Additional contact persons for legal entities or multi-person households.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `client_id` | UUID | NO | - | FK to clients.id (cascade delete) |
| `full_name` | VARCHAR(255) | NO | - | Contact full name |
| `phone` | VARCHAR(20) | YES | NULL | Phone number |
| `email` | VARCHAR(255) | YES | NULL | Email address |
| `position` | VARCHAR(100) | YES | NULL | Position (for legal entities) |
| `is_primary` | BOOLEAN | NO | FALSE | Primary contact flag |
| `notes` | TEXT | YES | NULL | Contact notes |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `is_primary` NOT NULL

**Foreign Keys:**
- `client_id` → `clients(id)` ON DELETE CASCADE

**Indexes:**
- `idx_client_contacts_client` — B-tree on `client_id`
- `idx_client_contacts_is_primary` — B-tree on `is_primary`

**Soft Delete:** No (child table, deleted with parent)

**Future AI Support:**
- `position` TEXT for AI-based role extraction
- `notes` TEXT for contact behavior analysis

---

### 5. properties

**Purpose:** Real estate assets (apartments, houses, commercial, land, etc.).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `property_type` | VARCHAR(20) | NO | - | Property type (apartment, house, commercial, land, townhouse, penthouse) |
| `status` | VARCHAR(20) | NO | 'available' | Property status (available, under_contract, sold, rented, archived, removed) |
| `deal_type` | VARCHAR(20) | NO | - | Deal type (sale, rent_short, rent_long, commercial) |
| `title` | VARCHAR(255) | NO | - | Property title |
| `description` | TEXT | YES | NULL | Property description |
| `address` | TEXT | NO | - | Property address |
| `area_total` | NUMERIC(10,2) | YES | NULL | Total area in m² |
| `area_living` | NUMERIC(10,2) | YES | NULL | Living area in m² |
| `rooms` | INTEGER | YES | NULL | Number of rooms |
| `floor` | INTEGER | YES | NULL | Floor number |
| `floors_total` | INTEGER | YES | NULL | Total floors in building |
| `price` | NUMERIC(15,2) | NO | - | Price or rent amount |
| `price_currency` | VARCHAR(3) | NO | 'RUB' | Currency (RUB, USD, EUR) |
| `price_per_meter` | NUMERIC(15,2) | NO | - | Price per square meter (computed) |
| `commission` | NUMERIC(15,2) | YES | 0 | Agency commission amount |
| `owner_id` | UUID | YES | NULL | FK to clients.id (owner) |
| `photos` | TEXT[] | NO | '{}' | Photo URLs array |
| `documents` | TEXT[] | NO | '{}' | Document URLs array |
| `notes` | TEXT | YES | NULL | Property notes |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `property_type` CHECK (property_type IN ('apartment', 'house', 'commercial', 'land', 'townhouse', 'penthouse'))
- `status` CHECK (status IN ('available', 'under_contract', 'sold', 'rented', 'archived', 'removed'))
- `deal_type` CHECK (deal_type IN ('sale', 'rent_short', 'rent_long', 'commercial'))
- `price_currency` CHECK (price_currency IN ('RUB', 'USD', 'EUR'))

**Foreign Keys:**
- `owner_id` → `clients(id)` ON DELETE SET NULL

**Indexes:**
- `idx_properties_status_deal` — B-tree on `status`, `deal_type`
- `idx_properties_type` — B-tree on `property_type`
- `idx_properties_owner` — B-tree on `owner_id`
- `idx_properties_price` — B-tree on `price`
- `idx_properties_area_total` — B-tree on `area_total`
- `idx_properties_rooms` — B-tree on `rooms`
- `idx_properties_created_at` — B-tree on `created_at`

**Soft Delete:** No (properties cannot be soft deleted, only archived/removed)

**Future AI Support:**
- `description` TEXT — AI-powered property description generation
- `photos` TEXT[] — Vision AI for property analysis (condition, amenities)
- `area_total`, `price` — Price per meter computation via AI anomaly detection
- `notes` TEXT — AI-powered property insights

---

### 6. deals

**Purpose:** Transaction records linking clients and properties.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `deal_type` | VARCHAR(20) | NO | - | Deal type (sale, rent_short, rent_long, commercial) |
| `status` | VARCHAR(20) | NO | 'negotiation' | Deal status (negotiation, contract_signing, deposit, legal_check, payment, closed, cancelled) |
| `property_id` | UUID | NO | - | FK to properties.id |
| `title` | VARCHAR(255) | NO | - | Deal title (auto-generated) |
| `description` | TEXT | YES | NULL | Deal description |
| `price` | NUMERIC(15,2) | NO | - | Deal price |
| `price_currency` | VARCHAR(3) | NO | 'RUB' | Currency |
| `commission` | NUMERIC(15,2) | YES | 0 | Agency commission |
| `commission_percent` | NUMERIC(5,2) | YES | NULL | Commission percentage (computed) |
| `deposit_amount` | NUMERIC(15,2) | YES | NULL | Deposit amount |
| `start_date` | DATE | NO | - | Deal start date |
| `end_date` | DATE | YES | NULL | Deal end date (for rent) |
| `closing_date` | DATE | YES | NULL | Deal closure date |
| `source` | VARCHAR(50) | NO | 'other' | Deal source (referral, site, direct, other) |
| `notes` | TEXT | YES | NULL | Deal notes |
| `created_by` | UUID | NO | - | FK to users.id |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `deal_type` CHECK (deal_type IN ('sale', 'rent_short', 'rent_long', 'commercial'))
- `status` CHECK (status IN ('negotiation', 'contract_signing', 'deposit', 'legal_check', 'payment', 'closed', 'cancelled'))
- `source` CHECK (source IN ('referral', 'site', 'direct', 'other'))
- `commission_percent` CHECK (commission_percent >= 0 AND commission_percent <= 100)

**Foreign Keys:**
- `property_id` → `properties(id)` ON DELETE RESTRICT
- `created_by` → `users(id)` ON DELETE RESTRICT

**Indexes:**
- `idx_deals_status` — B-tree on `status`
- `idx_deals_property` — B-tree on `property_id`
- `idx_deals_dates` — B-tree on `start_date`, `closing_date`
- `idx_deals_created_at` — B-tree on `created_at`

**Soft Delete:** No (deals cannot be soft deleted, only cancelled)

**Future AI Support:**
- `description` TEXT — AI-powered deal summary generation
- `source` — AI-based deal source analysis
- `commission_percent` — AI-based commission optimization suggestions

---

### 7. deal_participants

**Purpose:** Client roles in deals (buyer, seller, tenant, landlord, agent, witness).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `deal_id` | UUID | NO | - | FK to deals.id (cascade delete) |
| `client_id` | UUID | NO | - | FK to clients.id |
| `role` | VARCHAR(20) | NO | - | Participant role (buyer, seller, tenant, landlord, agent, witness) |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `role` CHECK (role IN ('buyer', 'seller', 'tenant', 'landlord', 'agent', 'witness'))

**Foreign Keys:**
- `deal_id` → `deals(id)` ON DELETE CASCADE
- `client_id` → `clients(id)` ON DELETE RESTRICT

**Indexes:**
- `idx_deal_participants_deal` — B-tree on `deal_id`
- `idx_deal_participants_client` — B-tree on `client_id`
- `idx_deal_participants_role` — B-tree on `role`

**Soft Delete:** No (junction table, deleted with parent)

**Future AI Support:**
- `role` — AI-based role extraction from client information
- `client_id` — AI-powered client-deal compatibility analysis

---

### 8. documents

**Purpose:** Files and documents related to clients, properties, or deals.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `document_type` | VARCHAR(20) | NO | - | Document type (contract, passport, extract, deed, receipt, statement, photo, video, report, other) |
| `status` | VARCHAR(20) | NO | 'pending' | Document status (pending, received, verified, expired, rejected) |
| `title` | VARCHAR(255) | NO | - | Document title |
| `description` | TEXT | YES | NULL | Document description |
| `file_name` | VARCHAR(255) | NO | - | Original file name |
| `file_path` | VARCHAR(500) | NO | - | Storage path |
| `file_size` | BIGINT | YES | NULL | File size in bytes |
| `file_hash` | VARCHAR(64) | YES | NULL | SHA-256 hash |
| `mime_type` | VARCHAR(100) | YES | NULL | MIME type |
| `client_id` | UUID | YES | NULL | FK to clients.id |
| `property_id` | UUID | YES | NULL | FK to properties.id |
| `deal_id` | UUID | YES | NULL | FK to deals.id |
| `uploaded_by` | UUID | NO | - | FK to users.id |
| `expiry_date` | DATE | YES | NULL | Expiration date |
| `notes` | TEXT | YES | NULL | Document notes |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `document_type` CHECK (document_type IN ('contract', 'passport', 'extract', 'deed', 'receipt', 'statement', 'photo', 'video', 'report', 'other'))
- `status` CHECK (status IN ('pending', 'received', 'verified', 'expired', 'rejected'))

**Foreign Keys:**
- `client_id` → `clients(id)` ON DELETE SET NULL
- `property_id` → `properties(id)` ON DELETE SET NULL
- `deal_id` → `deals(id)` ON DELETE SET NULL
- `uploaded_by` → `users(id)` ON DELETE RESTRICT

**Indexes:**
- `idx_documents_client` — B-tree on `client_id`
- `idx_documents_property` — B-tree on `property_id`
- `idx_documents_deal` — B-tree on `deal_id`
- `idx_documents_type_status` — B-tree on `document_type`, `status`
- `idx_documents_uploaded_by` — B-tree on `uploaded_by`
- `idx_documents_expiry_date` — B-tree on `expiry_date`

**Soft Delete:** No (documents cannot be soft deleted, only status changes)

**Future AI Support:**
- `file_hash` — AI-powered document similarity detection
- `mime_type` — AI-based document classification
- `file_size` — AI-based file anomaly detection
- `description` TEXT — AI-powered document summary generation

---

### 9. communications

**Purpose:** Interaction records (calls, emails, Telegram messages, meetings, etc.).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `communication_type` | VARCHAR(20) | NO | - | Communication type (call, email, telegram, whatsapp, meeting, site_message, note) |
| `direction` | VARCHAR(10) | NO | - | Direction (incoming, outgoing) |
| `client_id` | UUID | YES | NULL | FK to clients.id |
| `deal_id` | UUID | YES | NULL | FK to deals.id |
| `subject` | VARCHAR(255) | YES | NULL | Communication subject |
| `content` | TEXT | NO | - | Communication content |
| `duration` | INTEGER | YES | NULL | Duration in seconds (for calls) |
| `contact` | VARCHAR(255) | YES | NULL | Contact (phone/email/telegram username) |
| `assigned_to` | UUID | YES | NULL | FK to users.id |
| `is_important` | BOOLEAN | NO | FALSE | Important flag |
| `tags` | TEXT[] | NO | '{}' | Communication tags |
| `created_by` | UUID | NO | - | FK to users.id |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `communication_type` CHECK (communication_type IN ('call', 'email', 'telegram', 'whatsapp', 'meeting', 'site_message', 'note'))
- `direction` CHECK (direction IN ('incoming', 'outgoing'))

**Foreign Keys:**
- `client_id` → `clients(id)` ON DELETE SET NULL
- `deal_id` → `deals(id)` ON DELETE SET NULL
- `assigned_to` → `users(id)` ON DELETE SET NULL
- `created_by` → `users(id)` ON DELETE RESTRICT

**Indexes:**
- `idx_communications_client` — B-tree on `client_id`
- `idx_communications_deal` — B-tree on `deal_id`
- `idx_communications_assigned` — B-tree on `assigned_to`
- `idx_communications_type_created` — B-tree on `communication_type`, `created_at`
- `idx_communications_is_important` — B-tree on `is_important`

**Soft Delete:** No (communications cannot be soft deleted)

**Future AI Support:**
- `content` TEXT — AI-powered sentiment analysis, topic classification
- `is_important` BOOLEAN — AI-based importance scoring
- `tags` TEXT[] — AI-generated tags for communication categorization
- `duration` INTEGER — AI-based call quality analysis

---

### 10. tasks

**Purpose:** Action items for real estate agents.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | gen_random_uuid() | Primary key |
| `title` | VARCHAR(255) | NO | - | Task title |
| `description` | TEXT | YES | NULL | Task description |
| `status` | VARCHAR(20) | NO | 'pending' | Task status (pending, in_progress, completed, cancelled) |
| `priority` | VARCHAR(10) | NO | 'medium' | Task priority (low, medium, high, critical) |
| `task_type` | VARCHAR(20) | YES | 'other' | Task type (other, call, email, meeting, inspection, contract, payment) |
| `client_id` | UUID | YES | NULL | FK to clients.id |
| `deal_id` | UUID | YES | NULL | FK to deals.id |
| `property_id` | UUID | YES | NULL | FK to properties.id |
| `assigned_to` | UUID | NO | - | FK to users.id |
| `created_by` | UUID | NO | - | FK to users.id |
| `due_date` | TIMESTAMPTZ | YES | NULL | Due date |
| `completed_at` | TIMESTAMPTZ | YES | NULL | Completion timestamp |
| `completed_by` | UUID | YES | NULL | FK to users.id (completer) |
| `reminder` | TIMESTAMPTZ | YES | NULL | Reminder timestamp |
| `notes` | TEXT | YES | NULL | Task notes |
| `tags` | TEXT[] | NO | '{}' | Task tags |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last update timestamp |

**Constraints:**
- `status` CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled'))
- `priority` CHECK (priority IN ('low', 'medium', 'high', 'critical'))
- `task_type` CHECK (task_type IN ('other', 'call', 'email', 'meeting', 'inspection', 'contract', 'payment'))

**Foreign Keys:**
- `client_id` → `clients(id)` ON DELETE SET NULL
- `deal_id` → `deals(id)` ON DELETE SET NULL
- `property_id` → `properties(id)` ON DELETE SET NULL
- `assigned_to` → `users(id)` ON DELETE RESTRICT
- `created_by` → `users(id)` ON DELETE RESTRICT
- `completed_by` → `users(id)` ON DELETE SET NULL

**Indexes:**
- `idx_tasks_assigned_status` — B-tree on `assigned_to`, `status`
- `idx_tasks_due` — B-tree on `due_date`
- `idx_tasks_client` — B-tree on `client_id`
- `idx_tasks_deal` — B-tree on `deal_id`
- `idx_tasks_priority` — B-tree on `priority`
- `idx_tasks_created_at` — B-tree on `created_at`

**Soft Delete:** No (tasks cannot be soft deleted)

**Future AI Support:**
- `description` TEXT — AI-powered task prioritization
- `priority` VARCHAR(10) — AI-based priority reassignment
- `tags` TEXT[] — AI-generated tags for task categorization
- `reminder` TIMESTAMPTZ — AI-based reminder optimization

---

## Index Strategy

### High-Performance Indexes (Always Recommended)

1. **Composite Indexes for Common Queries:**
   - `idx_clients_type_status` — Filter by client type and status
   - `idx_properties_status_deal` — Filter active properties by deal type
   - `idx_deals_status` — Filter active deals
   - `idx_communications_client_created` — Client communication history
   - `idx_tasks_assigned_status` — User's pending tasks

2. **Foreign Key Indexes:**
   - All FK columns should be indexed for JOIN performance

3. **Partial Indexes for Soft Deletes:**
   - Create partial indexes for `status IN ('active', 'available')` queries to speed up filtered queries

4. **Full-Text Search Indexes:**
   - `address` column on `properties` for full-text search
   - `notes`, `description` columns on all entities for search

### Index Recommendations by Table

| Table | Recommended Indexes |
|-------|---------------------|
| `roles` | `name` (unique), `is_system` |
| `users` | `role_id`, `status`, `telegram_id`, `phone`, `email`, `created_at` |
| `clients` | `type`, `status`, `source`, `telegram_id`, `phone`, `created_at` |
| `client_contacts` | `client_id`, `is_primary` |
| `properties` | `status`, `deal_type`, `property_type`, `owner_id`, `price`, `area_total`, `rooms`, `created_at` |
| `deals` | `status`, `property_id`, `start_date`, `closing_date`, `created_at` |
| `deal_participants` | `deal_id`, `client_id`, `role` |
| `documents` | `client_id`, `property_id`, `deal_id`, `document_type`, `status`, `uploaded_by`, `expiry_date` |
| `communications` | `client_id`, `deal_id`, `assigned_to`, `communication_type`, `created_at`, `is_important` |
| `tasks` | `assigned_to`, `status`, `due_date`, `client_id`, `deal_id`, `property_id`, `priority`, `created_at` |

---

## Soft Delete Strategy

### Current Implementation
- No tables have `deleted_at` column
- Deletion is permanent (DELETE FROM table WHERE id = ...)
- Archive status (`archived`, `removed`, `cancelled`) used instead

### Future Migration Path
- Add `deleted_at TIMESTAMPTZ` to all tables
- Replace `DELETE` with `UPDATE ... SET deleted_at = NOW()`
- Create partial indexes for non-deleted records: `WHERE deleted_at IS NULL`
- Add `is_deleted` boolean for filtering convenience

### Example Migration
```sql
ALTER TABLE properties ADD COLUMN deleted_at TIMESTAMPTZ;
UPDATE properties SET deleted_at = NOW() WHERE status = 'removed';
CREATE INDEX idx_properties_deleted ON properties(deleted_at) WHERE deleted_at IS NULL;
```

---

## Audit Fields

All tables include:
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` — Record creation time
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` — Last update time

Update strategy:
- Use database triggers or ORM hooks to auto-update `updated_at`
- Use `NOW()` default for `created_at`

---

## Future AI Support

### AI-Ready Design Patterns

1. **JSONB for Flexible Metadata:**
   - `roles.permissions` — Store permission patterns for AI analysis
   - `users.settings` — Store AI preferences
   - `clients.tags` — AI-generated tags for lead scoring

2. **Vector Search Columns:**
   - Add `embedding` vector column to `documents` for semantic search
   - Add `embedding` vector column to `properties` for property similarity

3. **Timestamps for AI Analysis:**
   - `last_login` — User activity patterns
   `created_at`, `updated_at` — Change detection

4. **Text Analysis Columns:**
   - `description` TEXT — AI-powered content generation
   - `content` TEXT — AI-powered sentiment analysis
   - `notes` TEXT — AI-powered insights

5. **Classification Columns:**
   - `document_type`, `communication_type`, `task_type` — AI-based classification

---

## Related Documentation

- `docs/domain/domain_model.md` — Canonical domain model
- `docs/domain/entities.md` — PostgreSQL DDL (SQL generation follows)
- `docs/architecture/overview.md` — High-level architecture
- `docs/development_rules.md` — Development guidelines
