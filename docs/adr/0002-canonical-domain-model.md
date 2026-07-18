|# ADR-0002|

Date: 2026-06-07|

## Context

The Real Estate OS project needs a canonical domain model to guide backend implementation. The previous v1 model had 7 core entities but lacked detailed documentation, extensibility notes, and complete relationship coverage.

## Decision

Adopt a canonical domain model with 10 entities:

1. **User** — System users (agents, managers, support)
2. **Client** — Individual or legal entity clients
3. **ClientContact** — Additional contacts for legal entities
4. **Property** — Real estate assets
5. **Deal** — Transaction records
6. **DealParticipant** — Client roles in deals
7. **Document** — Files and documents
8. **Communication** — Interaction records
9. **Task** — Action items
10. **Role** — System roles with permissions

## Reason

- **Complete coverage:** All business areas (sales, rentals, commercial) supported
- **Clear relationships:** Explicit one-to-many and many-to-many relationships
- **Extensibility:** JSONB fields and documented extensibility paths
- **Database-ready:** Full PostgreSQL DDL with constraints and indexes
- **Future-proof:** Design principles prevent premature entity invention

## Status

Accepted
