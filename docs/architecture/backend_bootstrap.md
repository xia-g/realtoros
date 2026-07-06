# Backend Bootstrap Architecture V1

## Overview

The backend bootstrap defines the concrete implementation architecture for Real Estate OS. It translates the frozen domain model (ADR-0012) and all architectural decisions (ADRs 0001–0013) into a structured, layered backend written in Python 3.12+ with FastAPI, SQLAlchemy 2, Alembic, and PostgreSQL.

```
┌────────────────────────────────────────────────────────────┐
│                     Application Layers                      │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  API Layer (FastAPI routes)                          │  │
│  │  /api/v1/clients  /api/v1/properties  /api/v1/leads  │  │
│  │  /api/v1/deals    /api/v1/documents  /api/v1/graph   │  │
│  └─────────────────────────┬────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────┴────────────────────────────┐  │
│  │  Service Layer (business logic)                      │  │
│  │  ClientService  PropertyService  DealService         │  │
│  │  LeadService    DocumentService  GraphService        │  │
│  │  ScoringService CommunicationService  TaskService    │  │
│  └─────────────────────────┬────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────┴────────────────────────────┐  │
│  │  Repository Layer (data access)                      │  │
│  │  GenericRepository<T> → ClientRepository, etc.       │  │
│  └─────────────────────────┬────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────┴────────────────────────────┐  │
│  │  Domain Layer (models + enums)                       │  │
│  │  SQLAlchemy 2 models + Pydantic schemas              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│                  Cross-Cutting Layers                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │   CRM    │  │Knowledge │  │Telegram  │  │Integration│  │
│  │  Layer   │  │  Layer   │  │  Layer   │  │  Layer    │  │
│  │          │  │          │  │          │  │           │  │
│  │ clients  │  │ OCR      │  │ bot      │  │ Avito     │  │
│  │ leads    │  │ Classif. │  │ handlers │  │ CIAN      │  │
│  │ deals    │  │ Extract. │  │ review   │  │ parser    │  │
│  │ tasks    │  │ Graph    │  │ notify   │  │ API       │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│                    AI Layer                                 │
├────────────────────────────────────────────────────────────┤
│  Knowledge Agent  │  Scoring Engine  │  Embedding Service  │
│  Qwen Local       │  DeepSeek Flash  │  DeepSeek Pro       │
│  ChatGPT (fallback)                                        │
└────────────────────────────────────────────────────────────┘
```

---

## 1. Project Folder Structure

```
real-estate-os/
├── backend/
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Settings (pydantic-settings)
│   ├── database.py                      # Async engine + session factory
│   ├── exceptions.py                    # Global exception hierarchy
│   ├── logging_.py                      # Logging configuration
│   │
│   ├── models/                          # SQLAlchemy 2 declarative models
│   │   ├── __init__.py                  # re-export all models
│   │   ├── base.py                      # UUIDMixin, TimestampMixin
│   │   ├── role.py
│   │   ├── user.py
│   │   ├── client.py
│   │   ├── client_contact.py
│   │   ├── property.py
│   │   ├── deal.py
│   │   ├── deal_participant.py
│   │   ├── document.py
│   │   ├── communication.py
│   │   ├── task.py
│   │   ├── lead.py                      # NEW: ADR-0013
│   │   └── lead_event.py                # NEW: ADR-0013
│   │
│   ├── schemas/                         # Pydantic v2 request/response models
│   │   ├── __init__.py
│   │   ├── base.py                      # Pagination, common responses
│   │   ├── client.py
│   │   ├── property.py
│   │   ├── deal.py
│   │   ├── lead.py                      # NEW
│   │   └── ... (one per entity)
│   │
│   ├── repositories/                    # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py                      # GenericRepository[T]
│   │   ├── client.py
│   │   ├── property.py
│   │   ├── deal.py
│   │   ├── lead.py                      # NEW: status machine + event logging
│   │   └── ... (one per entity)
│   │
│   ├── services/                        # Business logic layer
│   │   ├── __init__.py
│   │   ├── base.py                      # BaseService
│   │   ├── client.py                    # ClientService
│   │   ├── property.py                  # PropertyService
│   │   ├── deal.py                      # DealService
│   │   ├── lead.py                      # LeadService (status machine, scoring)
│   │   ├── document.py                  # DocumentService
│   │   ├── communication.py             # CommunicationService
│   │   ├── task.py                      # TaskService
│   │   └── graph.py                     # GraphService
│   │
│   ├── api/                             # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── router.py                    # Master router → sub-routers
│   │   ├── dependencies.py              # DI: get_session, get_current_user
│   │   ├── clients.py                   # /api/v1/clients
│   │   ├── properties.py                # /api/v1/properties
│   │   ├── deals.py                     # /api/v1/deals
│   │   ├── leads.py                     # /api/v1/leads  (NEW)
│   │   ├── documents.py                 # /api/v1/documents
│   │   ├── communications.py            # /api/v1/communications
│   │   ├── tasks.py                     # /api/v1/tasks
│   │   ├── graph.py                     # /api/v1/graph
│   │   └── health.py                    # /health
│   │
│   ├── middleware/                      # FastAPI middleware
│   │   ├── __init__.py
│   │   ├── auth.py                      # JWT authentication
│   │   ├── audit.py                     # Request audit logging
│   │   └── error_handler.py             # Global exception handler
│   │
│   ├── migrations/                      # Alembic (per ADR-0003)
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   ├── make_migration.sh
│   │   └── versions/
│   │       ├── 2026_06_07_001_001_initial_schema.py
│   │       ├── 002_add_leads.py          # NEW
│   │       └── ...
│   │
│   └── tests/                           # Tests (per §12)
│       ├── conftest.py
│       ├── unit/
│       ├── integration/
│       └── fixtures/
│
├── ai/                                  # AI Layer
│   ├── __init__.py
│   ├── knowledge_agent/                 # Full pipeline per knowledge_agent_v1.md
│   │   ├── pipeline.py
│   │   ├── ingestion/
│   │   ├── ocr/
│   │   ├── classification/
│   │   ├── extraction/
│   │   ├── resolution/
│   │   ├── graph/
│   │   ├── storage/
│   │   ├── review/
│   │   └── mcp/
│   ├── scoring/                         # Lead scoring engine
│   │   ├── rule_based.py
│   │   ├── ml_model.py
│   │   └── config.py
│   ├── embeddings/                      # Entity embedding service
│   │   └── embedder.py
│   └── router.py                        # AI model router (Qwen/DeepSeek/ChatGPT)
│
├── bot/                                 # Telegram Layer (Aiogram 3)
│   ├── __init__.py
│   ├── bot.py                           # Bot initialization
│   ├── dispatcher.py                    # Router + filters
│   ├── handlers/                        # Message handlers
│   │   ├── lead_capture.py              # Lead creation from messages
│   │   ├── review.py                    # Review workflow callbacks
│   │   └── commands.py                  # /start, /help
│   ├── keyboards/                       # Inline keyboards
│   └── middlewares/                     # Throttling, auth
│
├── integrations/                        # Integration Layer
│   ├── avito/                           # Avito API client
│   ├── cian/                            # CIAN API client
│   └── base.py                          # Base integration class
│
├── scripts/                             # Utility scripts
├── data/                                # Runtime data (models, temp files)
└── docs/                                # Architecture docs (frozen per ADR-0012)
```

---

## 2. Configuration System

### Design

```python
class Settings(BaseSettings):
    """Single source of truth for all configuration.

    Loaded from .env file at project root.
    All settings are validated by Pydantic.
    No hardcoded config values anywhere in the codebase.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/real_estate_os"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/real_estate_os"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ── App ────────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False
    APP_TITLE: str = "Real Estate OS API"
    APP_VERSION: str = "0.2.0"
    APP_DESCRIPTION: str = "AI-платформа для агентства недвижимости"

    # ── Security ───────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440   # 24h
    JWT_ALGORITHM: str = "HS256"

    # ── Telegram ───────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    REVIEW_GROUP_CHAT_ID: str = ""

    # ── AI Models ──────────────────────────────────────
    AI_QWEN_ENDPOINT: str = "http://localhost:8001/v1"
    AI_DEEPSEEK_FLASH: str = "deepseek-chat"     # or remote endpoint
    AI_DEEPSEEK_PRO: str = "deepseek-reasoner"
    AI_CHATGPT_API_KEY: str = ""
    AI_EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"

    # ── Lead Scoring ──────────────────────────────────
    LEAD_SCORE_RULE_HOT: float = 0.80
    LEAD_SCORE_RULE_WARM: float = 0.60
    LEAD_SCORE_RULE_COLD: float = 0.30
    LEAD_AUTO_ASSIGN_THRESHOLD: float = 0.80
    LEAD_EXPIRY_DAYS: int = 30
    LEAD_MAX_REOPEN: int = 3

    # ── Integrations ──────────────────────────────────
    AVITO_API_KEY: str = ""
    CIAN_API_KEY: str = ""
```

### Category Grouping

Settings are organized into functional groups matching the business layers:

| Config Group | Purpose | Example |
|-------------|---------|---------|
| Database | Connection pool, echo, migrations | `DB_POOL_SIZE: 20` |
| App | Metadata, debug mode, versioning | `APP_TITLE`, `APP_DEBUG` |
| Security | JWT, token expiry, CORS | `SECRET_KEY` |
| Telegram | Bot token, API credentials, review group | `TELEGRAM_BOT_TOKEN` |
| AI Models | Endpoints, model names per task complexity | `AI_QWEN_ENDPOINT` |
| Lead Scoring | Thresholds, expiry settings | `LEAD_SCORE_RULE_HOT` |
| Integrations | External platform API keys | `AVITO_API_KEY` |

### Access Pattern

```python
# Single import pattern — no circular dependency risk
from backend.config import settings

# Usage anywhere in the codebase
async def some_service():
    if settings.APP_DEBUG:
        ...
```

---

## 3. Dependency Injection

### FastAPI Dependency Pattern

```python
# ── In api/dependencies.py ──────────────────────────

async def get_session() -> AsyncSession:
    """Yield an async database session.

    One session per request. Committed on success,
    rolled back on exception, always closed.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    token: str = Depends(oauth2_scheme),
) -> User:
    """Extract and validate JWT, return User.

    Used as a dependency on all authenticated routes.
    """
    payload = decode_jwt(token, settings.SECRET_KEY)
    user = await UserRepository(session).get(UUID(payload["sub"]))
    if not user or user.status != "active":
        raise HTTPException(status_code=401)
    return user


async def get_lead_service(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> LeadService:
    """Service with user context injection."""
    return LeadService(session=session, current_user=user)
```

### Service Injection Pattern

```python
# Service depends on session, optionally on current user
class LeadService:
    def __init__(
        self,
        session: AsyncSession,
        current_user: User | None = None,
    ):
        self.session = session
        self.current_user = current_user
        self.repo = LeadRepository(session)
        self.event_repo = LeadEventRepository(session)
```

### No Global State

- No global `db_session` variable
- No module-level service singletons
- All dependencies are created per-request via FastAPI's `Depends()`
- Background jobs create their own sessions

---

## 4. Database Session Management

### Existing Foundation (kept as-is)

```python
# backend/database.py — already correct
engine = create_async_engine(settings.DATABASE_URL, ...)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = DeclarativeBase
```

### Session Lifecycle

```
Request arrives
    │
    ▼
FastAPI dependency: get_session()
    │
    ▼
async_session_factory() → one session per request
    │
    ├─ Success → commit()
    ├─ Error   → rollback()
    └─ Finally → close()
    │
    ▼
Response sent
```

### Background Task Sessions

```python
# Background jobs create their own sessions
async def background_lead_scoring():
    async with async_session_factory() as session:
        try:
            scorer = LeadScoringService(session)
            await scorer.score_all_pending()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Session Per Repository?

Repository receives session from outside (not creating its own). This enables:

- Multiple repositories sharing one transactional session
- Service-level transaction control
- Unit of Work pattern across entities (e.g., Lead conversion touches leads + clients + deals + graph_edges)

---

## 5. Repository Pattern

### GenericRepository (existing, extended)

```python
class GenericRepository[T: Base]:
    """Generic async repository.

    All entity-specific repositories inherit from this.
    Extends base CRUD with soft-delete awareness.
    """

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def create(self, **kwargs) -> T
    async def get(self, id: UUID) -> T | None
    async def list(self, page, page_size, filters, order_by, descending) -> tuple[list[T], int]
    async def update(self, id: UUID, **kwargs) -> T | None
    async def delete(self, id: UUID) -> bool            # soft delete per ADR-0010
    async def hard_delete(self, id: UUID) -> bool        # admin only
```

### Repository Hierarchy

| Repository | Model | Extra Methods |
|-----------|-------|---------------|
| `GenericRepository[T]` | Any | Base CRUD |
| `ClientRepository` | Client | `find_by_phone`, `find_by_telegram`, `find_duplicates` |
| `LeadRepository` | Lead | `find_by_source`, `find_active_by_agent`, `find_for_scoring` |
| `LeadEventRepository` | LeadEvent | `find_by_lead`, `get_status_history`, `get_response_time` |
| `DealRepository` | Deal | `find_by_participant`, `get_pipeline_stats` |
| `PropertyRepository` | Property | `find_by_cadastral`, `search_by_address` |
| `DocumentRepository` | Document | `find_by_entity` (client/property/deal) |
| `CommunicationRepository` | Communication | `find_by_lead`, `get_timeline` |
| `TaskRepository` | Task | `find_by_assignee`, `get_overdue` |
| `GraphNodeRepository` | GraphNode | `find_by_entity`, `search_by_label` |
| `GraphEdgeRepository` | GraphEdge | `find_neighbors`, `find_path` |

### Soft Delete Implementation

```python
class GenericRepository[T]:
    async def list(self, ...) -> tuple[list[T], int]:
        stmt = select(self.model).where(
            self.model.deleted_at.is_(None)  # always filter deleted
        )
        # ... apply filters, pagination

    async def delete(self, id: UUID) -> bool:
        """Soft delete: set deleted_at instead of removing."""
        instance = await self.get(id)
        if not instance:
            return False
        instance.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def hard_delete(self, id: UUID) -> bool:
        """Permanent deletion (admin only)."""
        instance = await self.get(id)
        if not instance:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True
```

---

## 6. Service Layer Pattern

### Design Rules

1. **Service receives session**, creates repositories internally
2. **Business logic lives in services**, never in API handlers
3. **Services are stateless** — all state is in the database or passed as parameters
4. **Services call repositories** — never SQLAlchemy directly
5. **Services call other services** — cross-entity operations (e.g., LeadService calls ClientService on conversion)
6. **Services raise domain exceptions** — never HTTPException

### Service Hierarchy

| Service | Responsibilities |
|---------|-----------------|
| `ClientService` | CRUD, duplicate detection, enrichment |
| `LeadService` | Status machine, qualification, scoring trigger, conversion |
| `LeadScoringService` | Score computation, priority assignment, auto-assign |
| `DealService` | Pipeline management, commission calculation |
| `PropertyService` | Cadastral lookup, address matching |
| `DocumentService` | Upload workflow, entity linking |
| `CommunicationService` | Timeline, lead enrichment from messages |
| `TaskService` | Auto-creation from lead events, assignment |
| `GraphService` | Edge management, path queries, recommendations |
| `KnowledgePipelineService` | Orchestrates OCR → Classify → Extract → Resolve → Graph |

### Cross-Service Flow

```python
# Example: Lead → Client conversion (service orchestration)
class LeadService:
    async def convert_to_client(self, lead_id: UUID) -> Client:
        lead = await self.repo.get(lead_id)
        lead.assert_can_convert()  # status = qualified, has name + contact

        # 1. Match or create client
        client_service = ClientService(self.session, self.current_user)
        client = await client_service.find_or_create(
            full_name=lead.full_name,
            phone=lead.phone,
            email=lead.email,
            source="lead_conversion",
        )

        # 2. Update lead
        await self.repo.update(lead_id,
            status="converted",
            client_id=client.id,
            converted_at=datetime.now(timezone.utc),
        )

        # 3. Log event
        await self.event_repo.log_conversion(lead.id, client.id)

        # 4. Create graph edge
        graph_service = GraphService(self.session)
        await graph_service.create_edge(
            source_type="lead", source_id=lead.id,
            target_type="client", target_id=client.id,
            edge_type="converts_to",
        )

        # 5. Auto-create deal (if budget known)
        if lead.budget_max:
            deal_service = DealService(self.session, self.current_user)
            await deal_service.create_from_lead(lead, client)

        return client
```

---

## 7. API Layer Pattern

### Routing Structure

```python
# backend/api/router.py
api_router = APIRouter(prefix="/api/v1")

api_router.include_router(clients_router, prefix="/clients", tags=["clients"])
api_router.include_router(properties_router, prefix="/properties", tags=["properties"])
api_router.include_router(deals_router, prefix="/deals", tags=["deals"])
api_router.include_router(leads_router, prefix="/leads", tags=["leads"])
api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
api_router.include_router(communications_router, prefix="/communications", tags=["communications"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
```

### Route Handler Pattern

```python
# backend/api/clients.py
router = APIRouter()

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a client by ID."""
    service = ClientService(session=session, current_user=current_user)
    client = await service.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientResponse.model_validate(client)


@router.get("/", response_model=PaginatedResponse[ClientResponse])
async def list_clients(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List clients with optional filters."""
    service = ClientService(session=session, current_user=current_user)
    filters = {k: v for k, v in {"status": status, "type": type}.items() if v}
    items, total = await service.list(page=page, page_size=page_size, filters=filters)
    return PaginatedResponse(
        items=[ClientResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )
```

### Response Patterns

| Pattern | When | Example |
|---------|------|---------|
| `response_model=Model` | Single entity | `GET /clients/{id}` |
| `PaginatedResponse[T]` | List with pagination | `GET /clients/` |
| `CreatedResponse` | POST returns created entity | `POST /clients` |
| `NoContent (204)` | DELETE success | `DELETE /clients/{id}` |
| `ErrorResponse` | Validation errors | ValidationException handler |

---

## 8. Exception Hierarchy

```python
# backend/exceptions.py

class AppError(Exception):
    """Base application error. Caught by global handler."""

class NotFoundError(AppError):
    """Entity not found (→ 404)."""

class ValidationError(AppError):
    """Business rule violation (→ 422)."""

class ConflictError(AppError):
    """Duplicate / state conflict (→ 409)."""

class ForbiddenError(AppError):
    """Permission denied (→ 403)."""

class UnauthorizedError(AppError):
    """Authentication required (→ 401)."""

# ── Domain-specific ──

class LeadStateError(ValidationError):
    """Invalid state transition per ADR-0013 state machine."""

class LeadConversionError(ValidationError):
    """Lead cannot be converted (missing fields / wrong status)."""

class DealPipelineError(ValidationError):
    """Invalid deal status transition."""

class DuplicateEntityError(ConflictError):
    """Entity already exists (phone, cadastral, etc.)."""

class ScoringError(AppError):
    """Lead scoring computation failed."""

class KnowledgeAgentError(AppError):
    """Document processing pipeline error (→ 500)."""
```

### Global Error Handler

```python
# backend/middleware/error_handler.py

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """Map domain exceptions to HTTP responses."""
    status_map = {
        NotFoundError: 404,
        ValidationError: 422,
        ConflictError: 409,
        ForbiddenError: 403,
        UnauthorizedError: 401,
    }
    status = status_map.get(type(exc), 500)
    return JSONResponse(
        status_code=status,
        content={
            "error": type(exc).__name__,
            "detail": str(exc),
            "type": "validation" if status == 422 else "business",
        },
    )
```

---

## 9. Logging Architecture

```python
# backend/logging_.py

import logging
import structlog  # structured logging

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processors": [
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
        },
        "console": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "level": "DEBUG",
        },
        "json_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/app.log",
            "maxBytes": 10_000_000,  # 10 MB
            "backupCount": 5,
            "formatter": "json",
            "level": "INFO",
        },
    },
    "loggers": {
        "app": {                     # Application logger
            "handlers": ["console", "json_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "app.lead": {                # Lead lifecycle tracking
            "handlers": ["json_file"],
            "level": "INFO",
            "propagate": False,
        },
        "app.knowledge": {           # Document pipeline
            "handlers": ["json_file"],
            "level": "INFO",
            "propagate": False,
        },
        "sqlalchemy.engine": {       # DB queries (debug only)
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "aiobotocore": {             # External API calls
            "level": "WARNING",
        },
    },
}
```

### Logging Categories

| Logger | Purpose | Format | Retention |
|--------|---------|--------|-----------|
| `app` | General application events | JSON + console | 5 × 10 MB |
| `app.lead` | Lead lifecycle (create, convert, score, lost) | JSON only | 5 × 10 MB |
| `app.knowledge` | Document pipeline stages | JSON only | 5 × 10 MB |
| `app.security` | Auth events (login, token issue, failed auth) | JSON only | 30 × 10 MB |
| `app.integration` | External API calls (Avito, CIAN) | JSON only | 5 × 10 MB |

---

## 10. Audit Architecture

### Application-Level Audit

```python
# backend/middleware/audit.py

class AuditMiddleware(BaseHTTPMiddleware):
    """Logs all mutating API requests for audit.

    Captures: who, what, when, which entity, previous state.
    Stores in audit_log table for compliance.
    """

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next):
        if request.method in self.MUTATING_METHODS:
            # Capture request context before processing
            body = await request.body()
            start = time.time()

            response = await call_next(request)

            # Log after processing (includes response)
            await self._log_audit_event(
                user_id=request.state.user_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=int((time.time() - start) * 1000),
                request_body=body[:4096],  # truncate large payloads,
            )
            return response
        return await call_next(request)
```

### Audit Log Table

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    method VARCHAR(10) NOT NULL,         -- POST, PUT, PATCH, DELETE
    path VARCHAR(500) NOT NULL,          -- /api/v1/clients/{id}
    status_code INTEGER NOT NULL,
    duration_ms INTEGER,
    request_body TEXT,                   -- truncated to 4KB
    client_ip VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_path ON audit_log(path);
```

### Entity-Level Audit (via lead_events pattern)

The `lead_events` table (ADR-0013) serves as the template for entity-level audit tracing. The same pattern (event_type, from_state, to_state, changed_by, metadata JSONB) is used for other sensitive entities:

| Entity | Audit Table | Events Tracked |
|--------|-------------|----------------|
| Lead | `lead_events` | Status changes, scoring, assignment, conversion |
| Deal | `deal_events` (future) | Pipeline stages, price changes, document uploads |
| Client | `client_events` (future) | Type changes, status changes, merge events |

---

## 11. Background Jobs Strategy

### Design

Background jobs run as separate async tasks within the FastAPI process (for MVP) or as a separate worker process (for production).

```python
class BackgroundJobRegistry:
    """Registry of all background jobs.

    Jobs are:
    - Async functions that create their own DB session
    - Independent of request/response cycle
    - Scheduled via APScheduler or triggered by events
    """

    @staticmethod
    def get_jobs() -> list[JobDefinition]:
        return [
            # ── Lead Management ──
            JobDefinition(
                name="score_leads",
                interval_minutes=60,
                func="ai.scoring.jobs.score_all_pending_leads",
                description="Batch scoring for all active leads",
            ),
            JobDefinition(
                name="expire_stale_leads",
                interval_minutes=1440,  # daily
                func="backend.services.lead.expire_stale_leads",
                description="Auto-expire leads beyond LEAD_EXPIRY_DAYS",
            ),

            # ── AI Pipeline ──
            JobDefinition(
                name="retrain_classifier",
                interval_minutes=10080,  # weekly
                func="ai.classification.ml_classifier.retrain",
                description="Weekly ML classifier retraining",
            ),
            JobDefinition(
                name="compute_graph_ai_edges",
                interval_minutes=60,
                func="ai.knowledge_agent.graph.ai_builder.run_inferences",
                description="AI-inferred graph edges (same address, shared deals)",
            ),

            # ── Maintenance ──
            JobDefinition(
                name="cleanup_expired_edges",
                interval_minutes=1440,
                func="ai.knowledge_agent.graph.maintenance.cleanup_expired_edges",
                description="Remove time-bound graph edges",
            ),
            JobDefinition(
                name="recompute_embeddings",
                interval_minutes=1440,
                func="ai.embeddings.embedder.recompute_stale",
                description="Recompute embeddings for updated entities",
            ),
        ]
```

### Job Lifecycle

```
Scheduler tick (every N minutes)
    │
    ▼
Job: score_leads
    │
    ▼
async with async_session_factory() as session:
    │
    ├─ Query: all leads WHERE status NOT IN (converted, lost, spam)
    ├─ For each lead: compute score, update + log event
    └─ commit()
    │
    ▼
Next tick (or await next interval)
```

### Scheduling Options

| Option | For | Note |
|--------|-----|------|
| APScheduler | MVP | In-process, simple, no infra |
| Celery + Redis | Production | Distributed, retries, monitoring |
| Cron + management command | Simple tasks | `python -m backend.jobs.score_leads` |

---

## 12. Testing Architecture

### Test Structure

```
backend/tests/
├── conftest.py              # Fixtures: session, client, auth
├── unit/                    # Pure logic tests (no DB)
│   ├── test_lead_state_machine.py
│   ├── test_scoring_rules.py
│   └── test_address_normalizer.py
├── integration/             # DB + API tests
│   ├── test_client_api.py
│   ├── test_lead_api.py
│   ├── test_lead_conversion.py
│   └── test_pipeline_flow.py
└── fixtures/                # Test data
    ├── clients.json
    ├── leads.json
    └── documents/
```

### Fixture Strategy

```python
# conftest.py — async test infrastructure

@pytest_asyncio.fixture
async def db_session():
    """Create test database, run migrations, return session."""
    # Uses test database URL from env
    # Runs Alembic migrations once per session
    # Each test gets a transaction that is rolled back

@pytest_asyncio.fixture
async def client(db_session):
    """FastAPI TestClient with injected session."""
    app.dependency_overrides[get_session] = lambda: db_session
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest_asyncio.fixture
async def sample_lead(db_session):
    """Pre-created lead in test DB."""
    repo = LeadRepository(db_session)
    return await repo.create(
        source="telegram",
        source_id="-100123_456",
        full_name="Иванов Иван",
        phone="+79161234567",
        status="new",
    )
```

### What to Test Per Layer

| Layer | Test Type | What |
|-------|-----------|------|
| **Models** | Unit | Valid/invalid states, enum values, constraint checks |
| **Repositories** | Integration | CRUD, filters, pagination, soft delete |
| **Services** | Integration | Business rules, state machines, cross-entity flows |
| **API** | Integration | HTTP status codes, response schemas, auth, pagination |
| **State Machine** | Unit | Valid transitions, invalid transitions, edge cases |
| **Scoring** | Unit | Score computation, threshold mapping, priority assignment |

### Test Coverage Targets

| Layer | Target | Priority |
|-------|--------|----------|
| State machines (Lead, Deal) | 100% transition coverage | Critical |
| Scoring rules | 100% formula coverage | Critical |
| Services (business logic) | 90%+ branch coverage | High |
| API endpoints | 100% status code coverage | High |
| Repositories | 80%+ CRUD + filter coverage | Medium |
| Integration flows | Key flows (conversion, pipeline) | Critical |

---

## Layer Boundary Design

### Layer Map

```python
LAYER_BOUNDARIES = {
    "CRM Layer": {
        "path": "backend/services/",
        "entities": ["Client", "Lead", "Deal", "Property", "Task", "Communication"],
        "responsibility": "Business logic: CRUD, state machines, qualification, conversion",
        "depends_on": ["Repository Layer"],
        "called_by": ["API Layer", "Telegram Layer", "Knowledge Layer"],
        "calls": ["Repository Layer", "AI Layer (scoring)"],
    },
    "Knowledge Layer": {
        "path": "ai/knowledge_agent/",
        "entities": ["Document", "OCRResult", "Classification", "Extraction",
                      "Resolution", "GraphNode", "GraphEdge"],
        "responsibility": "Document pipeline: OCR → Classify → Extract → Resolve → Graph",
        "depends_on": ["CRM Layer (resolve existing entities)", "AI Layer (models)"],
        "called_by": ["API Layer", "MCP tools"],
        "calls": ["CRM Layer (entity lookup)", "AI Layer (OCR + LLM)"],
    },
    "Telegram Layer": {
        "path": "bot/",
        "entities": ["TelegramMessage", "TelegramUser"],
        "responsibility": "Lead capture, review workflow, agent notifications",
        "depends_on": ["CRM Layer (lead creation)", "AI Layer (message enrichment)"],
        "called_by": ["Telegram webhook"],
        "calls": ["CRM Layer (create lead)", "AI Layer (enrichment)"],
    },
    "Integration Layer": {
        "path": "integrations/",
        "entities": ["AvitoLead", "CIANLead"],
        "responsibility": "External platform ingestion: Avito, CIAN",
        "depends_on": ["CRM Layer (lead creation)"],
        "called_by": ["Scheduler (polling)", "Webhook (push)"],
        "calls": ["CRM Layer (create lead)"],
    },
    "AI Layer": {
        "path": "ai/",
        "entities": [],
        "responsibility": "Model routing, knowledge pipeline, scoring, embeddings",
        "depends_on": ["CRM Layer (entity data)"],
        "called_by": ["Knowledge Layer", "CRM Layer (scoring)", "Telegram Layer"],
        "calls": ["External LLM APIs", "CRM Layer (read entities)"],
    },
}
```

### Dependency Rules (enforced via import linter)

```
API Layer      → Service Layer  → Repository Layer  → Domain Layer
                    ↕                  ↕
               AI Layer          Knowledge Layer
                    ↕
               Telegram Layer / Integration Layer

RULES:
- API Layer  NEVER calls Repository Layer directly
- Services   NEVER import FastAPI (no HTTPException, no Request)
- Models     NEVER import services or repositories
- AI Layer   reads CRM entities but NEVER writes directly (must go through Service Layer)
- Knowledge Layer calls CRM services for entity resolution
- Telegram Layer calls CRM services for lead creation
```

### Concrete Example: Lead Created via Telegram

```
Telegram message arrives
    │
    ▼
Telegram Layer (bot/handlers/lead_capture.py)
    ├── Extracts: chat_id, username, message_text
    ├── Calls: LeadService.create(source='telegram', ...)
    │
    ▼
CRM Layer (backend/services/lead.py)
    ├── LeadRepository.create()
    ├── LeadEventRepository.log('created')
    ├── Applies scoring rules (rule-based)
    ├── Updates priority → warm
    │
    ▼
AI Layer (ai/scoring/rule_based.py)  ← async
    ├── Re-scores after enrichment
    │
    ▼
Telegram Layer (bot/keyboards/)  ← async
    ├── Sends confirmation to agent
```

---

## Summary: Architecture Decisions

| Decision | Choice | ADR Reference |
|----------|--------|---------------|
| Framework | FastAPI 0.110+ | ADR-0001 |
| ORM | SQLAlchemy 2.0+ (async) | ADR-0001 |
| Migrations | Alembic 1.13+ (async, date-named) | ADR-0003 |
| Database | PostgreSQL 17 | ADR-0001, ADR-0003 |
| Session per request | FastAPI Depends + context manager | — |
| Repository | GenericRepository[T] with soft delete | — |
| Service | Session + current_user injection | — |
| API routing | /api/v1/{entity} per entity | — |
| Config | pydantic-settings, single .env | — |
| Logging | structlog (JSON) + console | — |
| Audit | Per-request middleware + entity-level events | ADR-0010 |
| Background jobs | APScheduler (MVP), Celery (production) | — |
| Testing | pytest + httpx.AsyncClient | — |
| Soft delete | deleted_at on all tables | ADR-0010 |
| Exception hierarchy | AppError → HTTP mapping | — |
| Lead lifecycle | lead_events audit table | ADR-0013 |
| AI routing | Task → model table | ADR-0011 |

---

## Related Documentation

- `docs/architecture/audit_v1.md` — Known issues and critical path
- `docs/architecture/knowledge_agent_v1.md` — Document pipeline orchestrator
- `docs/domain/domain_model.md` — 11 entities with relationships
- `docs/domain/database_schema_v1.md` — ER Model V1
- `docs/adr/0012-architecture-freeze-v1.md` — Frozen architecture + change procedure
- `docs/adr/0013-lead-management-model.md` — Lead lifecycle and scoring
- `docs/development_rules.md` — AI model selection, coding rules
