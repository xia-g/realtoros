# Sprint 1 — Infrastructure Foundation

**Goal:** Production-ready backend infrastructure with no business logic.

**Duration:** 5 days
**Scope:** Configuration, database, SQLAlchemy models, Alembic migrations, logging, dependency injection, application bootstrap.

**No business APIs, no Telegram, no AI.**

---

## Current State

### What Already Exists

The project has a skeleton from an earlier bootstrap phase. These files exist but need review, extension, or hardening:

| File | State | Action |
|------|-------|--------|
| `backend/config.py` | Basic Settings class | Expand with all sections |
| `backend/database.py` | Correct async engine | Verify, keep as-is |
| `backend/main.py` | Basic FastAPI + lifespan | Rewrite with DI, middleware, structured startup |
| `backend/models/base.py` | UUIDMixin + TimestampMixin | Verify, keep as-is |
| `backend/models/role.py` through `task.py` | 10 models | Fix 19 missing `ondelete` clauses (audit C-1), add `deleted_at` (ADR-0010), add `__table_args__` with indexes |
| `backend/models/__init__.py` | All 10 models exported | Add Lead, LeadEvent |
| `backend/repositories/base.py` | GenericRepository[T] | Add soft delete, pagination hardening |
| `backend/services/base.py` | BaseService | Verify, keep as-is |
| `backend/migrations/env.py` | Async env with autogenerate | Verify, keep as-is |
| `backend/migrations/versions/001_...` | Initial 10-table migration | Keep as-is |
| `backend/api/router.py` | Basic 4-route router | Will keep but Sprint 1 scope is infra only |

### What Is Missing Entirely

| Artifact | Priority | Reason |
|----------|----------|--------|
| `backend/exceptions.py` | Critical | No global exception hierarchy exists |
| `backend/logging_.py` | Critical | No logging configuration exists |
| `backend/api/dependencies.py` | Critical | No DI setup exists |
| `backend/middleware/__init__.py` | High | No middleware package exists |
| `backend/middleware/error_handler.py` | High | No global error handler |
| `backend/middleware/audit.py` | High | No audit middleware |
| `backend/middleware/auth.py` | Medium | No JWT auth (not strictly needed yet) |
| `backend/models/lead.py` | High | ADR-0013 entity |
| `backend/models/lead_event.py` | High | ADR-0013 audit table |
| `backend/tests/conftest.py` | High | No test infrastructure |
| `backend/tests/unit/` | Medium | No unit tests |
| `backend/tests/integration/` | Medium | No integration tests |
| `.env` file | High | No env template |
| `.env.example` | Medium | No example env |

---

## Sprint 1 Task Breakdown

All estimates in engineer-hours (ideal). Total: **72 hours = 9 person-days**

### Phase 1: Foundation — Day 1 (16h)

#### T1: Configuration System (4h)

**Files:**
- `backend/config.py` — rewrite with all 7 sections
- `.env.example` — create with all keys documented
- `.env` — create (user creates from example)

**Acceptance Criteria:**
- Settings load from `.env` file
- All 7 config groups present (Database, App, Security, Telegram, AI, Scoring, Integrations)
- Default values for development
- `settings.APP_DEBUG` controls debug behaviour
- `from backend.config import settings` works without circular imports

**Implementation plan:**
```python
# 1. Define Settings class with all fields
# 2. Add SettingsConfigDict with env_file support
# 3. Create .env.example with all keys and comments
# 4. Create .env with development defaults
# 5. Verify import works
# 6. Verify settings.APP_VERSION == "0.2.0"
```

#### T2: Database Layer Hardening (4h)

**Files:**
- `backend/database.py` — verify + add connection retry settings

**Acceptance Criteria:**
- Async engine uses `settings.DATABASE_URL`
- Pool size = 20, max_overflow = 10
- `async_session_factory` produces `AsyncSession` with `expire_on_commit=False`
- `Base = DeclarativeBase` works
- `get_session()` dependency yields, commits, rollbacks, closes

**Implementation plan:**
```python
# Verify existing code is correct
# Add DB_ECHO from settings
# Test session lifecycle manually
```

#### T3: Exception Hierarchy (4h)

**Files:**
- `backend/exceptions.py` — NEW

**Acceptance Criteria:**
- Base `AppError(Exception)` exists
- 6 subclasses: NotFoundError (404), ValidationError (422), ConflictError (409), ForbiddenError (403), UnauthorizedError (401), ServiceError (500)
- Domain-specific: `LeadStateError(ValidationError)`, `DuplicateEntityError(ConflictError)`
- All exceptions accept `message: str` and optional `details: dict`
- `str(exc)` returns human-readable message

**Implementation plan:**
```python
class AppError(Exception):
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class NotFoundError(AppError): pass         # → 404
class ValidationError(AppError): pass       # → 422
class ConflictError(AppError): pass         # → 409
class ForbiddenError(AppError): pass        # → 403
class UnauthorizedError(AppError): pass     # → 401
class ServiceError(AppError): pass          # → 500

class LeadStateError(ValidationError): pass
class DuplicateEntityError(ConflictError): pass
```

#### T4: Logging Configuration (4h)

**Files:**
- `backend/logging_.py` — NEW

**Acceptance Criteria:**
- structlog configured with JSON rendering
- 5 loggers: `app`, `app.lead`, `app.knowledge`, `app.security`, `app.integration`
- Console handler (DEBUG) + rotating file handler (INFO)
- File rotation: 10 MB, 5 backups
- `from backend.logging_ import logger` works
- `logger.info("startup complete", extra={"version": settings.APP_VERSION})` produces valid JSON

**Implementation plan:**
```python
import structlog
import logging.config

LOGGING_CONFIG = { ... }  # dictConfig format

logging.config.dictConfig(LOGGING_CONFIG)
logger = structlog.get_logger("app")
```

---

### Phase 2: Domain Models — Day 2-3 (24h)

#### T5: Fix Missing `ondelete` on All Models (6h)

**Files (7 files affected):**
- `backend/models/user.py` — add `ondelete="RESTRICT"` to `role_id`
- `backend/models/property.py` — add `ondelete="SET NULL"` to `owner_id`
- `backend/models/deal.py` — add `ondelete="RESTRICT"` to `property_id`, `created_by`
- `backend/models/deal_participant.py` — add `ondelete="RESTRICT"` to `client_id`
- `backend/models/document.py` — add `ondelete="SET NULL"` to `client_id`, `property_id`, `deal_id`; `ondelete="RESTRICT"` to `uploaded_by`
- `backend/models/communication.py` — add `ondelete="SET NULL"` to `client_id`, `deal_id`, `assigned_to`; `ondelete="RESTRICT"` to `created_by`
- `backend/models/task.py` — add `ondelete="SET NULL"` to `client_id`, `deal_id`, `property_id`, `completed_by`; `ondelete="RESTRICT"` to `assigned_to`, `created_by`

**Acceptance Criteria:**
- All 19 missing ondelete clauses added
- Matches ER V1 specification exactly
- Models consistent with initial migration
- `python3 -m py_compile` passes on all files

**Verification:**
```python
# Spot-check: user.py should have ForeignKey("roles.id", ondelete="RESTRICT")
```

#### T6: Add `deleted_at` to All Models (4h)

**Files (10 files affected):**
- All model files: add `deleted_at: Mapped[datetime | None]`

**Acceptance Criteria:**
- `deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)` on all 10 models
- `base.py` TimestampMixin unchanged (deleted_at is NOT in TimestampMixin because Role and DealParticipant need it too)
- Soft delete is opt-in per model, not implicit

**Implementation plan:**
```python
# Add to each model class body:
deleted_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)
```

#### T7: Add Lead + LeadEvent Models (6h)

**Files:**
- `backend/models/lead.py` — NEW (ADR-0013)
- `backend/models/lead_event.py` — NEW (ADR-0013)
- `backend/models/__init__.py` — add Lead, LeadEvent imports

**Acceptance Criteria:**
- `Lead` model matches ADR-0013 specification:
  - Fields: id, source (Enum), source_id, source_metadata (JSONB), full_name, phone, email, telegram_id, telegram_username, interest_type (Enum), property_type, budget_min, budget_max, locations (ARRAY), status (Enum), previous_status, status_changed_at, score, score_components (JSONB), score_version, last_scored_at, priority, first_response_at, last_contact_at, assigned_to (FK→users), assigned_at, last_auto_assigned_at, qualified_by (FK→users), qualified_at, qualification_note, client_id (FK→clients), converted_at, deal_id (FK→deals), tags (ARRAY), notes, created_by (FK→users), deleted_at, created_at, updated_at
  - `leads.client_id` EXISTS, `clients.lead_id` DOES NOT (per review A)
  - No bidirectional FK
- `LeadEvent` model matches ADR-0013 specification:
  - Fields: id, lead_id (FK→leads, CASCADE), event_type, from_status, to_status, from_priority, to_priority, from_score, to_score, score_version, from_user_id (FK→users), to_user_id (FK→users), change_reason, changed_by (FK→users), metadata (JSONB), created_at
- Both models inherit UUIDMixin + TimestampMixin
- Both models have `__tablename__`, `__table_args__` with indexes from ADR-0013

#### T8: Add `__table_args__` with Indexes to All Models (4h)

**Files (all model files):**

**Acceptance Criteria:**
- Each model has `__table_args__` with all indexes from ER V1
- Composite indexes match the migration
- Index names match convention: `idx_{table}_{column(s)}`

**Implementation plan:**
```python
# Example for Property:
__table_args__ = (
    Index("idx_properties_status_deal", "status", "deal_type"),
    Index("idx_properties_type", "property_type"),
    Index("idx_properties_owner", "owner_id"),
    Index("idx_properties_price", "price"),
    Index("idx_properties_created_at", "created_at"),
)
```

#### T9: Add `audit_log` Model (4h)

**Files:**
- `backend/models/audit_log.py` — NEW

**Acceptance Criteria:**
- Fields: id (UUID PK), user_id (FK→users, nullable), method (VARCHAR 10), path (VARCHAR 500), status_code (Integer), duration_ms (Integer, nullable), request_body (Text, nullable), client_ip (VARCHAR 45, nullable), user_agent (Text, nullable), created_at (TIMESTAMPTZ)
- NOT in `__init__.py` yet (audit middleware not in Sprint 1 scope)
- Index on (created_at DESC), (user_id), (path)

---

### Phase 3: Application Bootstrap — Day 3-4 (16h)

#### T10: Dependency Injection Setup (4h)

**Files:**
- `backend/api/dependencies.py` — NEW

**Acceptance Criteria:**
- `get_session()` yields async database session
  - Creates session from `async_session_factory`
  - Yields to route handler
  - Commits on success
  - Rollbacks on exception
  - Always closes in finally block
- `get_current_user()` returns User from JWT token (stub — always returns None for Sprint 1)
- `get_optional_user()` returns User | None (for unauthenticated routes)
- `from backend.api.dependencies import get_session` works

**Verification:**
```python
# Manual test: start server, call GET /health, verify session lifecycle
```

#### T11: Global Error Handler (4h)

**Files:**
- `backend/middleware/__init__.py` — NEW (empty)
- `backend/middleware/error_handler.py` — NEW

**Acceptance Criteria:**
- `app_error_handler` catches all `AppError` subclasses
- Maps to correct HTTP status codes:
  - NotFoundError → 404
  - ValidationError → 422
  - ConflictError → 409
  - ForbiddenError → 403
  - UnauthorizedError → 401
  - ServiceError → 500
- `generic_error_handler` catches unhandled exceptions → 500 (logs full traceback)
- `http_exception_handler` keeps FastAPI HTTPException behaviour
- Response format: `{"error": "ExceptionName", "detail": "message", "type": "validation|auth|business|system"}`
- All handlers registered in `main.py` via `@app.exception_handler()`

**Implementation plan:**
```python
async def app_error_handler(request: Request, exc: AppError):
    status_map = { NotFoundError: 404, ValidationError: 422, ... }
    return JSONResponse(status_code=status_map.get(type(exc), 500), content={...})
```

#### T12: Audit Middleware Skeleton (4h)

**Files:**
- `backend/middleware/audit.py` — NEW

**Acceptance Criteria:**
- `AuditMiddleware` captures all POST, PUT, PATCH, DELETE requests
- Records: method, path, status_code, duration_ms, client_ip, user_agent
- Request body truncated to 4096 bytes
- Writes to `audit_log` table asynchronously (fire-and-forget via background task)
- Safe: never blocks the request, never causes 500 if audit write fails
- Registered in `main.py` via `app.add_middleware()`

**Implementation plan:**
```python
class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in MUTATING:
            start = time.time()
            response = await call_next(request)
            asyncio.create_task(self._log(request, response, time.time() - start))
            return response
        return await call_next(request)
```

#### T13: Application Bootstrap Rewrite (4h)

**Files:**
- `backend/main.py` — rewrite

**Acceptance Criteria:**
- Lifespan context manager:
  - Startup: configure logging, log startup event with version
  - Shutdown: dispose engine, log shutdown
- Middleware registered in correct order:
  1. CORSMiddleware (existing)
  2. AuditMiddleware
  3. Error handlers
- Router included: only health check for Sprint 1
- `GET /health` returns `{"status": "ok", "version": "0.2.0", "database": "connected|disconnected"}`
- Health check pings database to verify connectivity
- `python -m backend.main` starts uvicorn on `settings.APP_HOST:settings.APP_PORT`
- Application starts without any business routers registered

**Implementation plan:**
```python
@asynccontextmanager
async def lifespan(app):
    logger.info("Starting Real Estate OS API", version=settings.APP_VERSION)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    logger.info("Application shutdown complete")
```

---

### Phase 4: Migration + Testing — Day 4-5 (16h)

#### T14: Alembic Migration — Add Leads + Soft Delete (4h)

**Files:**
- `backend/migrations/versions/002_add_leads_and_soft_delete.py` — NEW

**Acceptance Criteria:**
- Migration creates `leads` and `lead_events` tables
- Migration adds `deleted_at TIMESTAMPTZ` to all 10 existing tables
- Migration updates clients CHECK constraint (remove 'lead' from status)
- Migration creates all indexes from ADR-0013
- `alembic upgrade head` succeeds on clean database
- `alembic downgrade -1` cleanly reverts

**Implementation plan:**
```sql
CREATE TABLE leads ( ... );  -- per ADR-0013
CREATE TABLE lead_events ( ... );
ALTER TABLE clients ADD COLUMN deleted_at TIMESTAMPTZ;
-- ... same for all 10 tables
ALTER TABLE clients DROP CONSTRAINT ... ;
ALTER TABLE clients ADD CONSTRAINT ... CHECK (status IN ('active', 'inactive', ...));
```

#### T15: Test Infrastructure (4h)

**Files:**
- `backend/tests/conftest.py` — NEW
- `backend/tests/unit/__init__.py` — NEW
- `backend/tests/unit/test_exceptions.py` — NEW
- `backend/tests/unit/test_config.py` — NEW
- `backend/tests/integration/__init__.py` — NEW
- `backend/tests/integration/test_database.py` — NEW
- `backend/tests/integration/test_health.py` — NEW

**Acceptance Criteria:**
- `conftest.py` fixtures:
  - `db_session()` — creates test database, runs migrations, yields session in transaction
  - `client()` — FastAPI TestClient with overridden dependencies
  - `sample_client()` — pre-created Client in test DB
  - `sample_lead()` — pre-created Lead in test DB (if migrations applied)
- `test_exceptions.py`:
  - All 6 AppError subclasses raise and catch correctly
  - str(exc) returns message
  - details dict preserved
- `test_config.py`:
  - Settings loads from .env
  - Default values for optional fields
- `test_database.py`:
  - Session creation and disposal
  - CRUD via GenericRepository
- `test_health.py`:
  - GET /health returns 200
  - Response contains status, version, database fields
- `pytest` discovers and runs all tests
- `pytest -x` stops on first failure

#### T16: Integration Smoke Test + CI Setup (4h)

**Files:**
- `.github/workflows/ci.yml` — NEW
- `scripts/setup_test_db.sh` — NEW
- `Makefile` — NEW

**Acceptance Criteria:**
- CI workflow:
  - Triggers on push to main + PR to main
  - Sets up Python 3.12
  - Installs dependencies from requirements.txt
  - Creates test PostgreSQL database
  - Runs Alembic migrations
  - Runs `pytest -x --cov=backend --cov-report=term`
- `Makefile` targets:
  - `make install` — create venv + pip install
  - `make migrate` — alembic upgrade head
  - `make test` — pytest
  - `make run` — uvicorn
  - `make clean` — remove __pycache__, .pyc
- `setup_test_db.sh` creates `real_estate_os_test` database

---

## Dependency Graph

```
T1 (config) ──► T2 (database) ──► T10 (DI) ──► T11 (errors) ──► T13 (bootstrap)
                                                      │
T5-T9 (models) ──► T14 (migration) ──► T15 (tests) ──┴──► T16 (CI)
```

Dependencies are directional. Tasks on the same horizontal level can be parallelized.

**Parallelisable groups:**
- T1 + T3 + T4 (config, exceptions, logging — no dependencies)
- T5 + T6 + T7 + T8 + T9 (model changes — all independent)
- T11 + T12 (error handler + audit — depend on T10)
- T15 + T16 (tests + CI — depend on all above)

---

## Effort Summary

| Phase | Tasks | Hours | Days | Engineers |
|-------|-------|-------|------|-----------|
| Foundation | T1–T4 | 16 | 1 | 2 |
| Domain Models | T5–T9 | 24 | 2 | 1–2 |
| Bootstrap | T10–T13 | 16 | 1 | 2 |
| Migration + Tests | T14–T16 | 16 | 1 | 2 |
| **Total** | **16 tasks** | **72** | **5** | **2** |

With 2 engineers working full-time: **4.5 calendar days.**

---

## Verification Checklist

After Sprint 1, the following commands should work:

```bash
# Application
cd /home/xiag/real-estate-os
source venv/bin/activate
python -m backend.main
# → uvicorn running on 0.0.0.0:8000
# → GET /health → {"status":"ok","version":"0.2.0","database":"connected"}

# Migrations
alembic upgrade head
alembic current           # → 002_add_leads_and_soft_delete (head)
alembic downgrade -1      # → reverts
alembic upgrade head      # → re-applies

# Tests
pytest -x                # → all tests pass
pytest --cov=backend --cov-report=term
# → coverage report

# Code quality
python3 -m py_compile backend/config.py
# → all model files compile cleanly
```

---

## Deliverables

### Files Created (8)
| File | Task |
|------|------|
| `backend/exceptions.py` | T3 |
| `backend/logging_.py` | T4 |
| `backend/api/dependencies.py` | T10 |
| `backend/middleware/__init__.py` | T11 |
| `backend/middleware/error_handler.py` | T11 |
| `backend/middleware/audit.py` | T12 |
| `backend/tests/conftest.py` | T15 |
| `Makefile` | T16 |

### Files Modified (18)
| File | Task |
|------|------|
| `backend/config.py` | T1 |
| `.env.example` | T1 |
| `backend/models/user.py` | T5, T6, T8 |
| `backend/models/property.py` | T5, T6, T8 |
| `backend/models/deal.py` | T5, T6, T8 |
| `backend/models/deal_participant.py` | T5, T6, T8 |
| `backend/models/document.py` | T5, T6, T8 |
| `backend/models/communication.py` | T5, T6, T8 |
| `backend/models/task.py` | T5, T6, T8 |
| `backend/models/client.py` | T6, T8 |
| `backend/models/client_contact.py` | T6, T8 |
| `backend/models/role.py` | T6, T8 |
| `backend/models/__init__.py` | T7 |
| `backend/main.py` | T13 |
| `backend/database.py` | T2 |

### Files Generated (2)
| File | Task |
|------|------|
| `backend/models/lead.py` | T7 |
| `backend/models/lead_event.py` | T7 |
| `backend/migrations/versions/002_add_leads_and_soft_delete.py` | T14 |

### Test Files (8)
| File | Task |
|------|------|
| `backend/tests/conftest.py` | T15 |
| `backend/tests/unit/__init__.py` | T15 |
| `backend/tests/unit/test_exceptions.py` | T15 |
| `backend/tests/unit/test_config.py` | T15 |
| `backend/tests/integration/__init__.py` | T15 |
| `backend/tests/integration/test_database.py` | T15 |
| `backend/tests/integration/test_health.py` | T15 |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PostgreSQL connection fails | Low | High | T2 includes connection retry config. T13 health check pings DB. |
| Existing migration conflicts with new model changes | Medium | High | T14 is separate migration version. Never modify applied migrations. |
| Async session management causes connection leaks | Low | High | T10 get_session() always closes in finally block. Pool size limit protects. |
| Audit middleware blocks request | Low | Medium | T12 uses fire-and-forget asyncio.create_task. Never awaits audit write. |
| Models compile but ondelete mismatch with migration | Medium | Medium | T5 explicitly checked against ER V1. Manual verification step. |

---

## Post-Sprint State

After Sprint 1, the project has:

```
real-estate-os/
├── backend/
│   ├── main.py                  # Production-ready FastAPI app
│   ├── config.py                # Full settings with 7 groups
│   ├── database.py              # Async pool, session factory, Base
│   ├── exceptions.py            # 6 AppError subclasses + domain-specific
│   ├── logging_.py              # structlog JSON + rotating files
│   ├── models/                  # 13 models with ondelete, deleted_at, indexes
│   ├── api/
│   │   └── dependencies.py      # get_session, get_current_user (stub)
│   ├── middleware/
│   │   ├── error_handler.py     # Global exception → HTTP mapping
│   │   └── audit.py             # Mutation logging (async, non-blocking)
│   ├── migrations/              # 001 (initial) + 002 (leads + soft delete)
│   └── tests/                   # conftest, unit tests, integration tests
├── .env.example                 # Documented configuration template
├── Makefile                     # install / migrate / test / run / clean
```

**What Sprint 1 explicitly does NOT ship:**
- No business API endpoints (no /clients, /leads, /deals, etc.)
- No Telegram integration
- No AI pipeline
- No authentication (get_current_user returns None stub)
- No business logic services
- No knowledge graph runtime
