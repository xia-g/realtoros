|# ADR-0003|

Date: 2026-06-07|

## Context

Domain model is approved. Need database schema V1 that supports PostgreSQL 16, UUID primary keys, soft delete, audit fields, and future AI integration.

## Decision

Design ER Model V1 with 10 tables based on canonical domain model:

1. `roles` — System roles with permissions
2. `users` — System users
3. `clients` — Clients
4. `client_contacts` — Additional contacts
5. `properties` — Real estate assets
6. `deals` — Transaction records
7. `deal_participants` — Deal participants
8. `documents` — Files and documents
9. `communications` — Interaction records
10. `tasks` — Action items

## Design Principles

- **UUID Primary Keys** — Distributed-friendly, sortable
- **Soft Delete** — Currently not implemented (archived status instead), migration path defined
- **Audit Fields** — `created_at`, `updated_at` on all tables
- **AI Support** — JSONB for flexible metadata, vector search columns planned
- **Foreign Key Constraints** — Referential integrity enforced
- **Index Strategy** — Composite indexes for common queries, partial indexes for soft deletes

## Reason

- **PostgreSQL 16** — Latest stable version with advanced features
- **UUID PKs** — No collisions, sortable, good for distributed systems
- **Soft Delete Ready** — Schema designed for future migration (add `deleted_at` column)
- **Audit Fields** — Complete audit trail for compliance and debugging
- **AI-Ready** — JSONB fields, timestamps, text analysis columns support future AI features
- **Performance** — Comprehensive index recommendations for common query patterns

## Status

Accepted
