# SQLAlchemy 2 Models — Implementation Plan

## Audit of Existing Models

All 10 models exist in `backend/models/`. Code audit results:

### What's Good
- Base model: UUIDMixin + TimestampMixin properly isolated
- All models use `from __future__ import annotations` for deferred annotation evaluation
- UUID primary keys via UUIDMixin
- Declarative model pattern (inheriting Base from database.py)
- Type hints everywhere (Mapped[str | None], etc.)
- JSONB for flexible metadata fields (users.settings, roles.permissions)
- ARRAY(String) for tags/photos

### Missing / Broken
1. **No `deleted_at` anywhere** — ER Model V1 defines soft-delete path but not yet implemented
2. **Missing `price_per_meter` on Property** — defined in domain model but absent in model
3. **Incomplete back_populates** — relationships are mostly one-directional:
   - `User` has no reverse relationships for tasks, communications, documents, deals
   - `Client` missing deal_participants, communications, documents, tasks relationships
   - `Property` missing documents, tasks relationships
   - `Deal` missing documents, communications, tasks relationships
4. **DealParticipant missing TimestampMixin** — ER V1 requires audit fields on all tables
5. **Document missing reverse relationships** — no client/property/deal back_populates
6. **Communication missing client/deal back_populates** — no reverse on Client.communications, Deal.communications
7. **Property missing `documents` column** — ER V1 has TEXT[] documents URLs field

### Models to Generate

| File | Status | Action |
|------|--------|--------|
| `base.py` | Good | Keep as-is |
| `__init__.py` | Good | Keep as-is |
| `role.py` | Good | Keep as-is |
| `user.py` | Partial | Add reverse relationships |
| `client.py` | Partial | Add missing relationships + properties.documents |
| `client_contact.py` | Good | Keep as-is |
| `property.py` | Partial | Add price_per_meter, documents field, reverse relationships |
| `deal.py` | Partial | Add missing relationships |
| `deal_participant.py` | Partial | Add TimestampMixin |
| `document.py` | Partial | Add reverse back_populates |
| `communication.py` | Partial | Add reverse back_populates |
| `task.py` | Partial | Add reverse back_populates |

### New Models Needed
- None (all 10 entities are covered)

### Dependency Order
1. base.py (kept as-is)
2. role.py (kept as-is)
3. user.py → depends on role.py
4. client.py → independent
5. client_contact.py → depends on client.py
6. property.py → depends on client.py
7. deal.py → depends on property.py, user.py
8. deal_participant.py → depends on deal.py, client.py
9. document.py → depends on client.py, property.py, deal.py, user.py
10. communication.py → depends on client.py, deal.py, user.py
11. task.py → depends on client.py, deal.py, property.py, user.py
12. __init__.py (kept as-is)
