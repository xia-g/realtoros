# Audit Log Architecture V1

## Overview

The Audit Log system provides an immutable, queryable trail of every critical business operation in Real Estate OS. It captures who did what, to which entity, when, and what the state was before and after.

```
┌──────────────────────────────────────────────────────────────┐
│                      Audit Trail                              │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐   │
│  │ API     │  │ Service  │  │ Knowledge │  │ Background │   │
│  │ Request │  │ Method   │  │ Agent     │  │ Job       │   │
│  └────┬────┘  └────┬─────┘  └─────┬─────┘  └─────┬─────┘   │
│       │            │              │               │         │
│       └────────────┴──────────────┴───────────────┘         │
│                            │                                 │
│                            ▼                                 │
│          ┌───────────────────────────────┐                   │
│          │       AuditService            │                   │
│          │                               │                   │
│          │  log(event) → INSERT into     │                   │
│          │  audit_log (immutable write)   │                   │
│          └───────────────────────────────┘                   │
│                            │                                 │
│                            ▼                                 │
│          ┌──────────────────────────────────────┐            │
│          │           audit_log TABLE             │            │
│          │  INSERT-only. No UPDATE. No DELETE.  │            │
│          └──────────────────────────────────────┘            │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 1. Audit Log Table

### DDL

```sql
-- Event type taxonomy
CREATE TYPE audit_event_type AS ENUM (
    -- Entity lifecycle
    'entity.created',           -- record created
    'entity.updated',           -- record updated
    'entity.deleted',           -- soft delete (deleted_at set)
    'entity.restored',          -- soft delete undone
    'entity.merged',            -- two records merged into one

    -- State machines
    'lead.status_changed',      -- lead status transition (per ADR-0013)
    'lead.qualified',           -- lead marked as qualified
    'lead.converted',           -- lead → client
    'lead.scored',              -- lead score recalculated
    'lead.assigned',            -- lead assigned to agent
    'deal.status_changed',      -- deal pipeline stage changed
    'deal.price_changed',       -- deal price modified
    'document.status_changed',  -- document processing status

    -- Security
    'auth.login',               -- user login
    'auth.logout',              -- user logout
    'auth.login_failed',        -- failed login attempt
    'auth.token_refreshed',     -- JWT token refresh
    'user.permission_changed',  -- role/permission modification

    -- Operations
    'import.completed',         -- bulk import finished
    'import.failed',            -- bulk import failed
    'rollback.executed',        -- data rollback performed
    'rollback.failed',          -- rollback could not complete

    -- AI / Knowledge Agent
    'ai.document_processed',    -- document pipeline completed
    'ai.extraction_completed',  -- entity extraction finished
    'ai.resolution_completed',  -- entity resolution finished
    'ai.graph_updated',         -- knowledge graph edge added
    'ai.model_invoked'          -- external AI model called

    -- Integrations
    'integration.lead_imported', -- lead from Avito/CIAN/Telegram
    'integration.webhook_received' -- external webhook
);

CREATE TYPE audit_entity_type AS ENUM (
    'client', 'lead', 'property', 'deal', 'deal_participant',
    'document', 'communication', 'task', 'user', 'role',
    'client_contact', 'lead_event',
    'graph_node', 'graph_edge',
    'pipeline_run', 'integration'
);


CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event classification
    event_type audit_event_type NOT NULL,
    entity_type audit_entity_type NOT NULL,
    entity_id UUID NOT NULL,                -- FK to the entity (no constraint — audit survives entity delete)

    -- Tenant (multi-agency support, future)
    tenant_id UUID,                          -- NULL for single-tenant deployments

    -- Who
    user_id UUID REFERENCES users(id),      -- NULL for system events
    user_email VARCHAR(255),                 -- denormalized for investigation speed
    user_name VARCHAR(255),                  -- denormalized

    -- Correlation (trace one operation across multiple audit entries)
    correlation_id UUID NOT NULL,            -- groups events from one operation
    request_id VARCHAR(64),                  -- HTTP request ID or job ID

    -- What changed
    before_state JSONB,                      -- full snapshot before change
    after_state JSONB,                       -- full snapshot after change
    changed_fields TEXT[],                    -- list of changed field names

    -- Context
    metadata JSONB DEFAULT '{}',
    -- Examples:
    -- {"reason": "Client requested deletion", "source_ip": "192.168.1.1"}
    -- {"merge_source_id": "uuid", "merge_reason": "duplicate_phone"}
    -- {"workflow": "knowledge_agent", "document_id": "uuid"}
    -- {"provider": "deepseek-flash", "tokens": 1500, "cost": 0.00015}

    -- Source attribution
    source_ip VARCHAR(45),                   -- client IP
    user_agent TEXT,                         -- HTTP user agent
    source_component VARCHAR(50),            -- 'api' | 'knowledge_agent' | 'telegram_bot' | 'integration' | 'scheduler'

    -- Immutable timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Core indexes
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_event ON audit_log(event_type, created_at DESC);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_log_correlation ON audit_log(correlation_id);
CREATE INDEX idx_audit_log_request ON audit_log(request_id);
CREATE INDEX idx_audit_log_tenant ON audit_log(tenant_id, created_at DESC);
CREATE INDEX idx_audit_log_component ON audit_log(source_component, created_at DESC);

-- GIN index for JSONB metadata queries
CREATE INDEX idx_audit_log_metadata ON audit_log USING GIN (metadata jsonb_path_ops);
```

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **PK** | UUID | Distributed-friendly, no sequential guessing |
| **event_type** | PostgreSQL ENUM | Type safety, autocomplete in queries, documentation |
| **entity_type** | PostgreSQL ENUM | Exhaustive list of auditable entities |
| **entity_id** | No FK constraint | Audit trail must survive entity deletion |
| **user_id** | FK nullable | FK enforced when user exists; NULL for system events |
| **user_email, user_name** | Denormalized | Avoid JOIN for 90% of investigation queries |
| **correlation_id** | UUID | Groups all events from one operation (e.g., lead conversion generates 5+ audit events) |
| **before_state / after_state** | JSONB | Full snapshot enables point-in-time reconstruction |
| **changed_fields** | TEXT[] | Quick filtering: "what fields changed?" without parsing JSON |
| **metadata** | JSONB | Flexible: any extra context without schema changes |
| **source_ip / user_agent** | VARCHAR/TEXT | Security investigations |
| **source_component** | VARCHAR | Trace which system component generated the event |
| **tenant_id** | UUID nullable | Multi-agency support. NULL for single-tenant. Indexed for tenant-scoped investigations. |
| **created_at** | Only timestamp | No `updated_at` — records are immutable |

---

## 2. Audit Event Types

### Entity Lifecycle Events (4)

| Event | When | before_state | after_state | Metadata |
|-------|------|-------------|-------------|----------|
| `entity.created` | New record inserted | NULL | Full new state | source |
| `entity.updated` | Existing record modified | State before update | State after update | changed_fields |
| `entity.deleted` | Soft delete (deleted_at set) | State before delete | State after delete (deleted_at now set) | reason |
| `entity.restored` | Soft delete undone | deleted_at set | deleted_at NULL | reason |
| `entity.merged` | Two records merged | Both records' states | Surviving record's final state | merge_source_id, merge_reason |

### Lead Events (6)

| Event | When | before_state | after_state | Metadata |
|-------|------|-------------|-------------|----------|
| `lead.status_changed` | ADR-0013 status transition | Lead with old status | Lead with new status | from_status, to_status |
| `lead.qualified` | Lead marked qualified | Pre-qualification state | Post-qualification state | qualified_by |
| `lead.converted` | Lead → Client + optional Deal | Lead + newly created Client ID | Client full state | deal_id (optional) |
| `lead.scored` | Score recalculated | old score, old components | new score, new components | score_version |
| `lead.assigned` | Agent assignment | old assigned_to | new assigned_to | auto_assigned (bool) |

### Deal Events (2)

| Event | When | before_state | after_state | Metadata |
|-------|------|-------------|-------------|----------|
| `deal.status_changed` | Pipeline stage change | old status | new status | stage_change_reason |
| `deal.price_changed` | Price modification | old price, commission | new price, commission | changed_by |

### Security Events (4)

| Event | When | before_state | after_state | Metadata |
|-------|------|-------------|-------------|----------|
| `auth.login` | Successful login | NULL | NULL | source_ip, user_agent |
| `auth.logout` | Explicit logout | NULL | NULL | session_id |
| `auth.login_failed` | Failed login attempt | NULL | NULL | attempt_count, failure_reason |
| `user.permission_changed` | Role/permission change | old role, old permissions | new role, new permissions | changed_by |

### Operations Events (2)

| Event | When | before_state | after_state | Metadata |
|-------|------|-------------|-------------|----------|
| `rollback.executed` | Rollback performed | State before rollback | State after rollback | affected_entities, reason |
| `import.completed` | Bulk import done | NULL | NULL | entity_type, count, source |

### AI Events (5)

| Event | When | before_state | after_state | Metadata |
|-------|------|-------------|-------------|----------|
| `ai.document_processed` | Full pipeline done | NULL | NULL | document_id, duration_ms, confidence |
| `ai.extraction_completed` | Entities extracted | NULL | extracted_data: {count per type} | document_id, model_used |
| `ai.model_invoked` | AI model called | NULL | NULL | provider, model, tokens, cost, duration_ms |
| `ai.graph_updated` | Graph edges added | NULL | edge_count | source: fk/extraction/ai |

### Integration Events (1)

| Event | When | before_state | after_state | Metadata |
|-------|------|-------------|-------------|----------|
| `integration.lead_imported` | Lead from external source | NULL | Lead state | source: avito/cian/telegram, source_id |

---

## 3. JSONB Storage Strategy

### before_state / after_state

These store a FULL snapshot of the entity at the time of the event. The snapshot includes:

```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "Иванов Иван Иванович",
    "phone": "+79161234567",
    "status": "active",
    "type": "buyer",
    "source": "lead_conversion",
    "created_at": "2026-06-01T10:00:00Z",
    "updated_at": "2026-06-07T14:30:00Z"
}
```

**Rules:**
- `before_state` = NULL for `entity.created` events
- `after_state` = NULL for `entity.deleted` events (after_state would be redundant — only deleted_at changed)
- Snapshots include ALL columns except: `deleted_at`, `embedding`, `password_hash`
- `password_hash` is NEVER stored in audit log (PII security)
- `embedding` is NEVER stored (vector is large and not human-readable)

### metadata JSONB

Flexible container for event-specific context:

```json
// Lead conversion metadata
{
    "source_lead_id": "550e8400-e29b-41d4-a716-446655440001",
    "created_client_id": "550e8400-e29b-41d4-a716-446655440002",
    "created_deal_id": "550e8400-e29b-41d4-a716-446655440003",
    "conversion_duration_days": 14,
    "confidence": 0.92,
    "model_used": "deepseek-pro",
    "agent_name": "Петров Пётр"
}

// AI model invocation metadata
{
    "provider": "deepseek",
    "model": "deepseek-chat",
    "input_tokens": 3450,
    "output_tokens": 420,
    "cost": 0.000387,
    "duration_ms": 2340,
    "task_type": "extract_contract",
    "fallback_used": false,
    "error": null
}

// Rollback metadata
{
    "affected_entities": ["client:uuid1", "deal:uuid2", "lead:uuid3"],
    "rollback_reason": "Incorrect extraction from document X",
    "document_id": "uuid",
    "executed_by": "user:uuid"
}
```

### changed_fields

A simple text array listing which fields were modified:

```sql
changed_fields = ARRAY['status', 'price', 'commission']
```

This enables fast queries like "find all events where price changed":

```sql
SELECT * FROM audit_log
WHERE 'price' = ANY(changed_fields)
  AND entity_type = 'deal'
  AND created_at >= NOW() - INTERVAL '30 days';
```

---

## 4. Correlation ID

Every business operation generates one `correlation_id` that is shared across ALL audit log entries produced by that operation.

### Correlation ID Flow

```python
# Example: Lead Conversion (one operation → 5 audit events)

correlation_id = uuid4()

audit_service.log(
    event_type="lead.status_changed",
    entity_type="lead",
    entity_id=lead.id,
    correlation_id=correlation_id,
    before_state={"status": "qualified"},
    after_state={"status": "converted"},
    metadata={"to_status": "converted"},
)

audit_service.log(
    event_type="entity.created",
    entity_type="client",
    entity_id=client.id,
    correlation_id=correlation_id,
    before_state=NULL,
    after_state=client_snapshot,
)

audit_service.log(
    event_type="lead.converted",
    entity_type="lead",
    entity_id=lead.id,
    correlation_id=correlation_id,
    before_state=lead_before,
    after_state=lead_after,
    metadata={"created_client_id": client.id, "created_deal_id": deal.id},
)

audit_service.log(
    event_type="entity.created",
    entity_type="deal",
    entity_id=deal.id,
    correlation_id=correlation_id,
    before_state=NULL,
    after_state=deal_snapshot,
)

audit_service.log(
    event_type="ai.graph_updated",
    entity_type="graph_edge",
    entity_id=NULL,
    correlation_id=correlation_id,
    before_state=NULL,
    after_state=NULL,
    metadata={"edge_count": 3, "source": "conversion"},
)
```

### Query by Correlation

```sql
-- Get complete audit trail for one operation
SELECT event_type, entity_type, entity_id, user_name,
       changed_fields, metadata, created_at
FROM audit_log
WHERE correlation_id = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY created_at;
```

---

## 5. AuditService

```python
class AuditService:
    """Central service for writing audit log entries.

    This is the ONLY class that writes to the audit_log table.
    All components (API handlers, services, Knowledge Agent,
    background jobs) call AuditService.log() — never INSERT directly.

    Thread-safe: uses its own database session.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        event_type: str,               # "entity.created"
        entity_type: str,              # "client"
        entity_id: UUID | None,
        user_id: UUID | None = None,
        user_email: str | None = None,
        user_name: str | None = None,
        correlation_id: UUID | None = None,  # auto-generated if None
        request_id: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        changed_fields: list[str] | None = None,
        metadata: dict | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        source_component: str = "api",
    ) -> UUID:
        """Write an immutable audit log entry."""

    async def log_event(
        self,
        event: AuditEvent,           # typed dataclass
    ) -> UUID:
        """Alternate entry point: accepts a pre-built AuditEvent."""

    async def log_from_context(
        self,
        context: AuditContext,       # current request context
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None,
    ) -> UUID:
        """Convenience: fills user/correlation/request/source from context."""
```

### AuditEvent Dataclass

```python
@dataclass
class AuditEvent:
    event_type: str
    entity_type: str
    entity_id: UUID | None
    user_id: UUID | None = None
    user_email: str | None = None
    user_name: str | None = None
    correlation_id: UUID | None = None
    request_id: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    changed_fields: list[str] | None = None
    metadata: dict | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    source_component: str = "api"
```

---

## 6. AuditContext

```python
@dataclass
class AuditContext:
    """Request-scoped audit context.

    Created once per request by middleware, passed through
    the dependency chain. Populates user, correlation, and
    source fields automatically.
    """
    user_id: UUID | None
    user_email: str | None
    user_name: str | None
    correlation_id: UUID           # one per request
    request_id: str | None
    source_ip: str | None
    user_agent: str | None
    source_component: str

    @classmethod
    def from_request(
        cls,
        request: Request,
        current_user: User | None,
    ) -> "AuditContext":
        """Create audit context from a FastAPI request."""
        return cls(
            user_id=current_user.id if current_user else None,
            user_email=current_user.email if current_user else None,
            user_name=current_user.full_name if current_user else None,
            correlation_id=uuid4(),
            request_id=request.headers.get("X-Request-ID"),
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            source_component="api",
        )

    @classmethod
    def system_context(cls) -> "AuditContext":
        """For background jobs and system operations."""
        return cls(
            user_id=None,
            user_email=None,
            user_name="System",
            correlation_id=uuid4(),
            request_id=None,
            source_ip=None,
            user_agent=None,
            source_component="scheduler",
        )

    @classmethod
    def for_knowledge_agent(cls) -> "AuditContext":
        """For Knowledge Agent pipeline operations."""
        return cls(
            user_id=None,
            user_email=None,
            user_name="Knowledge Agent",
            correlation_id=uuid4(),
            request_id=None,
            source_ip=None,
            user_agent=None,
            source_component="knowledge_agent",
        )
```

### Audit Context Flow

```
Request arrives → AuditMiddleware creates AuditContext
                       │
                       ▼
              AuditContext injected via Depends()
                       │
                       ▼
              Service method receives AuditContext
                       │
                       ▼
              Service calls AuditService.log_from_context(ctx, ...)
                       │
                       ▼
              audit_log INSERT (immutable)
```

---

## 7. AuditMiddleware

```python
class AuditMiddleware(BaseHTTPMiddleware):
    """Captures mutating API requests and logs them.

    For every POST/PUT/PATCH/DELETE:
    1. Captures request body (truncated to 4096 bytes)
    2. Creates AuditContext with correlation_id
    3. Stores AuditContext in request.state for downstream access
    4. After response: logs entity.updated / entity.created / entity.deleted
       based on method + status code

    This middleware handles the "generic" audit for simple CRUD.
    Complex operations (lead conversion, deal pipeline, AI pipeline)
    add their OWN audit events with richer context via AuditService directly.
    """

    EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/metrics"}

    async def dispatch(self, request, call_next):
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Create audit context
        ctx = AuditContext.from_request(request, request.state.user)

        # Store in request.state for downstream services
        request.state.audit_context = ctx

        # Capture request for potential audit
        body = await request.body() if request.method in MUTATING else None

        start = time.time()
        response = await call_next(request)
        duration = int((time.time() - start) * 1000)

        # Log CRUD audit for mutating methods
        if request.method in MUTATING and 200 <= response.status_code < 300:
            event_type = self._method_to_event(request.method)
            entity_type = self._path_to_entity(request.url.path)

            if event_type and entity_type:
                asyncio.create_task(
                    self._log_crud(
                        ctx=ctx,
                        event_type=event_type,
                        entity_type=entity_type,
                        entity_id=self._extract_id(request.url.path),
                        duration_ms=duration,
                        request_body=body[:4096] if body else None,
                    )
                )

        return response
```

### Integration with Service Layer

```python
# In api/dependencies.py:
async def get_audit_context(
    request: Request,
) -> AuditContext:
    """Inject audit context from middleware or create new."""
    ctx = getattr(request.state, "audit_context", None)
    if ctx:
        return ctx
    return AuditContext.from_request(request, current_user=None)


async def get_audit_service(
    session: AsyncSession = Depends(get_session),
    ctx: AuditContext = Depends(get_audit_context),
) -> AuditService:
    """Injectable audit service with context pre-filled."""
    return AuditService(session=session, context=ctx)


# In services/lead.py:
class LeadService:
    async def convert_to_client(self, lead_id: UUID) -> Client:
        audit = AuditService(self.session)

        # Each significant step gets its own audit event
        # All share the same correlation_id from request context

        lead_before = self._snapshot(lead)
        client = await self._create_client(lead)
        audit.log(
            event_type="entity.created",
            entity_type="client",
            entity_id=client.id,
            correlation_id=self.ctx.correlation_id,
            after_state=self._snapshot(client),
        )

        audit.log(
            event_type="lead.converted",
            entity_type="lead",
            entity_id=lead.id,
            before_state=lead_before,
            after_state=self._snapshot(lead),
            metadata={"created_client_id": client.id},
        )
```

---

## 8. Snapshot Strategy

```python
class EntitySnapshot:
    """Creates safe snapshots of entities for audit storage.

    Rules:
    - NEVER include password_hash, embedding, or raw binary data
    - ALWAYS include id, status, and critical business fields
    - Snapshots are dictionaries, not SQLAlchemy model instances
    """

    SENSITIVE_FIELDS = {"password_hash", "embedding", "name_embedding"}

    EXCLUDED_RELATIONSHIPS = {
        "client": {"contacts", "properties", "deal_participations",
                   "communications", "documents", "tasks"},
        "user": {"role"},
    }

    @staticmethod
    def take(entity: Base, depth: str = "shallow") -> dict:
        """
        shallow: entity fields only (no relationships)
        deep: entity fields + direct relationships (use sparingly)
        """
        snapshot = {}
        for column in entity.__table__.columns:
            if column.name in EntitySnapshot.SENSITIVE_FIELDS:
                continue
            value = getattr(entity, column.name)
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            if isinstance(value, Decimal):
                value = float(value)
            if isinstance(value, UUID):
                value = str(value)
            snapshot[column.name] = value

        if depth == "deep":
            rels = EntitySnapshot.EXCLUDED_RELATIONSHIPS.get(
                entity.__tablename__, set()
            )
            for rel_name in entity.__mapper__.relationships.keys():
                if rel_name in rels:
                    continue
                rel_value = getattr(entity, rel_name, None)
                if rel_value is not None:
                    if isinstance(rel_value, list):
                        snapshot[rel_name] = [
                            EntitySnapshot.take(r, "shallow")
                            for r in rel_value[:5]  # max 5 for deep
                        ]
                    else:
                        snapshot[rel_name] = EntitySnapshot.take(
                            rel_value, "shallow"
                        )

        return snapshot
```

---

## 9. Query Patterns

### Investigations

```sql
-- Who changed this client and what did they do?
SELECT a.event_type, a.changed_fields,
       a.user_name, a.created_at,
       a.before_state->>'status' AS old_status,
       a.after_state->>'status' AS new_status
FROM audit_log a
WHERE a.entity_type = 'client'
  AND a.entity_id = :client_id
ORDER BY a.created_at DESC;

-- What happened around this lead conversion?
SELECT a.event_type, a.entity_type, a.user_name,
       a.metadata, a.created_at
FROM audit_log a
WHERE a.correlation_id = (
    SELECT correlation_id FROM audit_log
    WHERE event_type = 'lead.converted'
      AND entity_id = :lead_id
    LIMIT 1
)
ORDER BY a.created_at;

-- Find all entities modified by a specific user in the last 24h
SELECT a.event_type, a.entity_type, a.entity_id,
       a.changed_fields, a.created_at
FROM audit_log a
WHERE a.user_id = :user_id
  AND a.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY a.created_at DESC;

-- Find all rollbacks this month
SELECT a.entity_type, a.entity_id,
       a.metadata->>'rollback_reason' AS reason,
       a.created_at
FROM audit_log a
WHERE a.event_type = 'rollback.executed'
  AND a.created_at >= DATE_TRUNC('month', NOW());

-- Cost summary by AI provider
SELECT a.metadata->>'provider' AS provider,
       COUNT(*) AS calls,
       SUM((a.metadata->>'cost')::numeric) AS total_cost
FROM audit_log a
WHERE a.event_type = 'ai.model_invoked'
  AND a.created_at >= DATE_TRUNC('month', NOW())
GROUP BY a.metadata->>'provider'
ORDER BY total_cost DESC;

-- Audit trail for a specific document pipeline run
SELECT a.event_type, a.source_component,
       a.metadata->>'confidence' AS confidence,
       a.metadata->>'duration_ms' AS duration,
       a.created_at
FROM audit_log a
WHERE a.correlation_id = (
    SELECT correlation_id FROM audit_log
    WHERE event_type = 'ai.document_processed'
      AND a.metadata->>'document_id' = :doc_id
    LIMIT 1
)
ORDER BY a.created_at;
```

### Retention

```sql
-- Count events by month
SELECT DATE_TRUNC('month', created_at) AS month,
       COUNT(*) AS events
FROM audit_log
GROUP BY month
ORDER BY month DESC;

-- Estimated size
SELECT pg_size_pretty(pg_table_size('audit_log')) AS table_size,
       pg_size_pretty(pg_indexes_size('audit_log')) AS indexes_size;
```

---

## 10. Retention Policy

| Tier | Retention | Action | Trigger |
|------|-----------|--------|---------|
| Hot | 90 days | Online in primary table | — |
| Warm | 1 year | Move to `audit_log_archive` table (same schema, different tablespace) | Daily job for events > 90 days |
| Cold | 3 years | Compressed CSV export to object storage | Monthly job for events > 1 year |
| Deleted | 7 years | Encrypted archive, then permanent delete | After 7 years |

**Implementation:**

```sql
-- Archive table (same schema, different physical storage)
CREATE TABLE audit_log_archive (LIKE audit_log INCLUDING ALL)
TABLESPACE archive_tablespace;

-- Move job (daily)
INSERT INTO audit_log_archive SELECT * FROM audit_log
WHERE created_at < NOW() - INTERVAL '90 days'
ORDER BY created_at
LIMIT 10000;

DELETE FROM audit_log
WHERE id IN (
    SELECT id FROM audit_log_archive
    WHERE created_at < NOW() - INTERVAL '90 days'
    LIMIT 10000
);
```

---

## 11. Performance Considerations

| Index | Purpose | Write Overhead | Query Benefit |
|-------|---------|---------------|---------------|
| `idx_audit_log_created` | Recent events, time-based queries | Low | High |
| `idx_audit_log_entity` | Entity-specific investigations | Low | Critical |
| `idx_audit_log_user` | User activity investigations | Low | High |
| `idx_audit_log_correlation` | Operation grouping | Low | Critical |
| `idx_audit_log_metadata` | JSONB queries (cost, provider) | Medium | High |

### Write Performance

| Scenario | Estimated Rate | Insert Time | Daily Volume |
|----------|---------------|-------------|--------------|
| Normal CRUD operations | 10 events/min | < 1 ms | 14,400 |
| Knowledge Agent pipeline | 50 events/doc | < 2 ms | 7,200 (at 144 docs/day) |
| AI model invocations | 100 events/hour | < 1 ms | 2,400 |
| Integration imports | 200 events/batch | < 1 ms | 2,000 |
| **Total estimate** | **~26,000 events/day** | — | **~500 MB/year** |

### Partitioning Strategy (Future)

At > 10M rows, partition by month:

```sql
CREATE TABLE audit_log (
    id UUID,
    event_type audit_event_type,
    ...
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_log_2026_06 PARTITION OF audit_log
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE audit_log_2026_07 PARTITION OF audit_log
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
```

Not required for MVP. Deferred until > 5M rows.

---

## 12. Integration with Existing Audit Systems

### Relationship to `lead_events`

The `lead_events` table (ADR-0013) serves as a LEAD-SPECIFIC audit trail with typed fields for status/score/priority transitions. The `audit_log` table is the GENERAL-PURPOSE audit trail for ALL entities.

```python
DUAL_AUDIT_RULE = """
For lead status transitions:
  lead_events and audit_log are BOTH written.
  
  lead_events: typed fields (from_status, to_status, from_score, to_score),
               optimized for lead analytics (conversion time, pipeline bottlenecks).
  
  audit_log:   generic fields (before_state, after_state JSONB),
               optimized for investigations (who did what, correlation across entities).
  
  They serve different query patterns and are NOT duplicates.
"""
```

### Relationship to `pipeline_events` (Knowledge Runtime)

The `pipeline_events` table from the Knowledge Processing Runtime is a STAGE-SPECIFIC audit trail for document processing. It tracks retries, durations, and model usage per pipeline stage.

```python
DUAL_AUDIT_RULE = """
For document pipeline events:
  pipeline_events and audit_log are BOTH written.
  
  pipeline_events: high-frequency, stage-level tracking (retries, durations, errors).
  audit_log:       summarizes the COMPLETED operation (document processed, entities created).
  
  pipeline_events: operational observability (how long did OCR take?)
  audit_log:       business audit (who uploaded what, what entities were created?)
"""
```

### Not Duplicated

- `audit_log` is the ONLY audit table for: entity CRUD, security events, rollbacks, integrations
- `lead_events` is NOT duplicated in `audit_log` — `lead_events` has typed fields for analytics
- `pipeline_events` is NOT duplicated in `audit_log` — `pipeline_events` has stage-level timings

---

## 13. Examples

### Example 1: Lead Status Change

```
correlation_id: a1b2c3d4
request_id: req-001
source_component: api

Event 1:
  event_type: lead.status_changed
  entity_type: lead
  entity_id: L-001
  user_name: Петров Пётр (agent)
  before_state: {status: "new", priority: "cold", score: 0.0}
  after_state:  {status: "contact_made", priority: "warm", score: 0.5}
  changed_fields: [status, priority, score]
  metadata: {to_status: "contact_made", auto: false}
```

### Example 2: Lead Conversion

```
correlation_id: e5f6g7h8
source_component: api

Event 1: lead.status_changed
  entity_type: lead → status "qualified" → "converted"

Event 2: entity.created
  entity_type: client
  after_state: {full_name: "Иванов Иван", phone: "+79161234567", ...}

Event 3: lead.converted
  metadata: {source_lead_id: "L-001", created_client_id: "C-001"}

Event 4: entity.created
  entity_type: deal
  after_state: {price: 8500000, status: "negotiation", ...}
```

### Example 3: Knowledge Agent Commit

```
correlation_id: i9j0k1l2
source_component: knowledge_agent

Event 1: ai.document_processed
  metadata: {document_id: "D-001", duration_ms: 45000, confidence: 0.87}

Event 2: entity.created (client)
  after_state: {full_name: "Петров Пётр", ...}

Event 3: entity.created (property)
  after_state: {address: "ул. Ленина, д.5", ...}

Event 4: ai.graph_updated
  metadata: {edge_count: 7, source: "extraction"}

Event 5: ai.model_invoked
  metadata: {provider: "deepseek", model: "deepseek-pro", tokens: 4500, cost: 0.00225}
```

### Example 4: Telegram Lead Ingestion

```
correlation_id: m3n4o5p6
source_component: telegram_bot

Event 1: integration.lead_imported
  entity_type: lead
  after_state: {source: "telegram", source_id: "-100123_456",
                full_name: "Сидоров Сидор", phone: null, ...}
  metadata: {source: "telegram", source_id: "-100123_456",
             username: "sidorov", chat_type: "private"}

Event 2: entity.created
  entity_type: lead
  after_state: {same as above}
```

### Example 5: Rollback

```
correlation_id: q7r8s9t0
source_component: api

Event 1: rollback.executed
  metadata: {rollback_reason: "Incorrect extraction from document",
             affected_entities: ["client:C-001", "deal:D-001"],
             document_id: "D-002"}

Event 2: entity.deleted (client)
  before_state: {full_name: "Ошибочный Клиент", ...}
  metadata: {reason: "rollback from document D-002"}

Event 3: entity.deleted (deal)
  before_state: {price: 1000000, ...}
  metadata: {reason: "rollback from document D-002"}
```

---

## 14. Schema Changes (ADR Required)

The following changes are required to existing frozen tables:

### New Table
- `audit_log` — (covered in §1)

### New ENUMs
- `audit_event_type` — 28 values across 8 categories
- `audit_entity_type` — 16 entity types

### Changes to Existing Tables (per ADR-0010)

Already covered by ADR-0010 (Soft Delete):
- `clients.created_by` — add FK to users
- `properties.created_by` — add FK to users
- `client_contacts.created_by` — add FK to users
- `deal_participants.created_by` — add FK to users

### Migration

```sql
-- Migration 005_add_audit_log.sql

CREATE TYPE audit_event_type AS ENUM (...);  -- 28 values
CREATE TYPE audit_entity_type AS ENUM (...); -- 16 values

CREATE TABLE audit_log (...);  -- full DDL from §1

CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);
-- ... all 7 indexes from §1
```

---

## 15. Related Documentation

- `docs/adr/0010-soft-delete-and-audit.md` — Soft delete foundation
- `docs/adr/0013-lead-management-model.md` — lead_events table (complementary audit)
- `docs/architecture/backend_bootstrap.md` — Middleware, service layer patterns
- `docs/architecture/knowledge_runtime.md` — pipeline_events table (complementary audit)
- `docs/architecture/audit_log.md` — This document
