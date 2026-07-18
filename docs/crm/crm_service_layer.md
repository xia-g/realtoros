# CRM Service Layer Architecture

**Date:** 2026-06-07  
**Sprint:** 2  
**Pre-requisites:** Sprint 1 (Infrastructure), Sprint 1B (Runtime Foundation)  

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                       │
│  /api/v1/leads  /clients  /properties  /deals  /tasks  /docs    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Depends(get_session())
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer (business)                    │
│  LeadService   ClientService   PropertyService                   │
│  DealService   TaskService     CommunicationService              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Conversion Engine: lead → client → deal (atomic txn)       │  │
│  │ State Machine:   status transitions with validation        │  │
│  │ Audit Events:    LeadEvent creation on every change        │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Repository Layer (data)                      │
│  GenericRepository[T]                                            │
│    ├── LeadRepository      find_by_source(), find_duplicates()   │
│    ├── ClientRepository    find_by_phone(), merge()              │
│    ├── PropertyRepository  find_by_owner()                       │
│    ├── DealRepository      find_by_client(), add_participant()   │
│    ├── DocumentRepository  find_by_hash()                        │
│    ├── TaskRepository      find_by_assignee()                    │
│    └── CommunicationRepo   find_by_client()                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SQLAlchemy Models + PostgreSQL                │
│   12 tables (roles, users, clients, properties, deals, ...)      │
│   Soft delete (deleted_at), Partial unique indexes               │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Service Architecture

### LeadService

```
create_lead(source, source_id, ...)    → Lead + LeadEvent
assign_lead(lead_id, user_id)           → Lead + LeadEvent
change_status(lead_id, new_status)      → Lead + LeadEvent (validated)
score_lead(lead_id, score)             → Lead + LeadEvent
qualify_lead(lead_id, qualified_by)     → Lead + LeadEvent
convert_lead(lead_id, converted_by)     → ConversionResult
merge_leads(primary, secondary)         → Lead (secondary archived)
archive_lead(lead_id)                   → soft delete
```

### Conversion Engine (convert_lead)

Atomic transaction:

```
1. Validate: lead.status == "qualified"
2. CREATE Client (from lead data)
3. UPDATE Lead: status → "converted"
4. CREATE LeadEvent: "lead_converted"
5. OPTIONAL: CREATE Deal with Client as participant
6. FLUSH (single transaction)
```

On any failure → rollback (session exception propagates to DI).

### ClientService

```
create_client(full_name, phone, ...)   → Client
update_client(id, ...)                  → Client
merge_clients(primary, secondary)       → Client
archive_client(id)                      → soft delete
find_duplicates(phone, email)           → list[Client]
get_client_history(id)                  → dict (client + related entities)
```

### PropertyService

```
create_property(address, ...)          → Property
update_property(id, ...)                → Property
assign_owner(id, owner_id)             → Property
attach_document(property_id, doc_id)   → Property
detach_document(property_id, doc_id)   → Property
archive_property(id)                    → soft delete
get_property_history(id)                → dict (property + related entities)
```

### DealService

```
create_deal(deal_type, participants, ...)  → Deal
change_status(id, new_status)               → Deal (validated)
attach_property(id, property_id)           → Deal
add_participant(id, client_id, role)       → DealParticipant
remove_participant(id, client_id)          → None
close_deal(id)                              → Deal (status → "closed")
cancel_deal(id)                             → Deal (status → "cancelled")
```

### TaskService

```
create_task(title, ...)         → Task
assign_task(id, user_id)        → Task
complete_task(id, completed_by) → Task
reopen_task(id)                 → Task
archive_task(id)                → soft delete
```

### CommunicationService

```
create_communication(type, content, ...)  → Communication
link_client(id, client_id)                → Communication
link_deal(id, deal_id)                    → Communication
assign_owner(id, user_id)                 → Communication
```

## 3. Lead State Machine (ADR-0013)

```
                    ┌─────────┐
                    │   new   │
                    └────┬────┘
                  ┌──────┴──────┐
                  ▼             ▼
            ┌──────────┐   ┌──────┐
            │contact_  │   │ lost │
            │made      │   └──────┘
            └─────┬────┘
                  ▼
            ┌──────────┐
            │qualifying│
            └─────┬────┘
                  ▼
            ┌──────────┐
            │qualified │
            └─────┬────┘
            ┌─────┴──────┐
            ▼            ▼
       ┌──────────┐   ┌──────┐
       │converted │   │ lost │
       └──────────┘   └──────┘

    Lost → Qualifying (re-engage)
    Archived: terminal state
```

## 4. Deal State Machine

```
negotiation → offer_made → under_review → approved → closed
     │            │             │            │
     └────────────┴─────────────┴────────────┘
                       │
                   cancelled
```

## 5. Repository Architecture

### GenericRepository[T]

```
create(**kwargs)         → T
get(id: UUID)            → T | None (active filter)
list(page, page_size)    → tuple[list[T], int] (active filter)
update(id, **kwargs)     → T | None
delete(id)               → bool (soft delete)
restore(id)              → T | None
hard_delete(id)          → bool (admin only)
exists(**filters)        → bool
count(**filters)         → int
```

### Entity Repositories

| Repository | Custom Methods |
|-----------|----------------|
| LeadRepository | `find_by_source()`, `find_by_phone()`, `find_duplicates()`, `find_active_leads()` |
| ClientRepository | `find_by_phone()`, `find_by_email()`, `find_duplicates()`, `find_by_name()` |
| PropertyRepository | `find_by_owner()`, `find_by_status()` |
| DealRepository | `find_active()`, `find_by_client()`, `find_by_property()` |
| DocumentRepository | `find_by_hash()`, `find_by_client()`, `find_by_property()`, `find_by_deal()` |
| TaskRepository | `find_by_assignee()`, `find_by_client()`, `find_pending()` |
| CommunicationRepository | `find_by_client()`, `find_by_deal()`, `find_by_assignee()` |

## 6. Audit Integration

Every service operation logs through structlog with structured fields:

```python
logger.info("lead_created", lead_id=..., source=..., phone=...)
logger.info("lead_converted", lead_id=..., client_id=..., deal_id=...)
logger.info("deal_created", deal_id=..., participants=...)
```

LeadService additionally creates `LeadEvent` records for all state changes:

| Event Type | Trigger |
|-----------|---------|
| `lead_created` | create_lead() |
| `lead_assigned` | assign_lead() |
| `status_changed` | change_status() |
| `score_changed` | score_lead() |
| `lead_qualified` | qualify_lead() |
| `lead_converted` | convert_lead() |
| `lead_merged` | merge_leads() |

## 7. API Structure

| Method | Endpoint | Service |
|--------|----------|---------|
| POST | /api/v1/leads | create_lead |
| GET | /api/v1/leads | lead_repo.list |
| GET | /api/v1/leads/{id} | lead_repo.get |
| PATCH | /api/v1/leads/{id} | lead_repo.update |
| DELETE | /api/v1/leads/{id} | archive_lead |
| POST | /api/v1/leads/{id}/assign | assign_lead |
| POST | /api/v1/leads/{id}/score | score_lead |
| POST | /api/v1/leads/{id}/qualify | qualify_lead |
| POST | /api/v1/leads/{id}/convert | convert_lead |
| POST | /api/v1/clients | create_client |
| GET | /api/v1/clients | list |
| GET | /api/v1/clients/{id} | get |
| PATCH | /api/v1/clients/{id} | update |
| DELETE | /api/v1/clients/{id} | archive |
| POST | /api/v1/properties | create_property |
| ... | ... | ... |
| POST | /api/v1/tasks | create_task |
| POST | /api/v1/tasks/{id}/complete | complete_task |
| POST | /api/v1/tasks/{id}/reopen | reopen_task |

## 8. Files Created

```
backend/
  repositories/
    __init__.py          (updated — all repos registered)
    base.py              (updated — restore(), exists(), count())
    lead_repository.py   (7 methods)
    client_repository.py (5 methods)
    property_repository.py (3 methods)
    deal_repository.py   (4 methods)
    document_repository.py (5 methods)
    task_repository.py   (4 methods)
    communication_repository.py (4 methods)
  services/
    __init__.py          (all services)
    lead_service.py      (10 methods + conversion engine)
    client_service.py    (7 methods)
    property_service.py  (9 methods)
    deal_service.py      (9 methods)
    task_service.py      (6 methods)
    communication_service.py (5 methods)
  schemas/
    __init__.py          (all schemas)
    common.py            (TimestampMixin, PaginatedResponse)
    lead.py              (Create, Update, Response)
    client.py            (Create, Update, Response)
    property.py          (Create, Update, Response)
    deal.py              (Create, Update, Response)
    task.py              (Create, Update, Response)
  api/
    router.py            (updated — leads, tasks, documents routes)
    routes/
      leads.py           (10 endpoints)
      tasks.py           (8 endpoints)
      documents.py       (3 endpoints)
  tests/
    unit/services/
      __init__.py
      test_lead_service.py      (22 tests)
      test_client_service.py    (8 tests)
      test_deal_service.py      (7 tests)
      test_task_service.py      (8 tests)
```

## 9. Known Limitations

| # | Limitation | Impact | Resolution |
|---|-----------|--------|------------|
| L1 | `get_current_user()` returns stub | Created_by is always None from API | Sprint 3 (JWT) |
| L2 | No pagination helper on services | API returns flat lists | Sprint 3 |
| L3 | No event sourcing for non-lead entities | Only LeadEvent exists | Sprint 4 |
| L4 | No validation for `budget_min ≤ budget_max` | Only application-level | Future migration |
| L5 | No webhook integration | No real-time notifications | Sprint 5 |
| L6 | No RBAC in services | Permission check is caller's responsibility | Sprint 3 |

## 10. End-to-End Workflow

```python
# Complete CRM lifecycle
async def demo_workflow(session):
    lead_svc = LeadService(session)
    deal_svc = DealService(session)
    task_svc = TaskService(session)
    comm_svc = CommunicationService(session)

    # 1. Create lead from Telegram
    lead = await lead_svc.create_lead(
        source="telegram",
        source_id="tg_user_123",
        full_name="Ivan Petrov",
        phone="+79001234567",
        interest_type="buy",
    )

    # 2. Assign to agent
    lead = await lead_svc.assign_lead(lead.id, agent_id)

    # 3. Qualify
    lead = await lead_svc.qualify_lead(lead.id, qualified_by=agent_id)

    # 4. Convert → creates Client + optional Deal
    result = await lead_svc.convert_lead(
        lead.id, converted_by=agent_id, create_deal=True,
    )

    # 5. Create follow-up task
    task = await task_svc.create_task(
        title="Prepare contract for Ivan Petrov",
        client_id=result.client.id,
        deal_id=result.deal.id,
        created_by=agent_id,
    )

    # 6. Log communication
    comm = await comm_svc.create_communication(
        communication_type="call",
        content="Discussed terms, client agrees to proceed",
        client_id=result.client.id,
        deal_id=result.deal.id,
        created_by=agent_id,
    )
```

All 6 steps are transactional, audited, and soft-delete compatible.
