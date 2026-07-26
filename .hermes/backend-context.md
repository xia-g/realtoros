# RealtorOS — Backend Context (MCP Developer Reference)
Generated 2026-07-25 | Root: `/home/xiag/real-estate-os/backend`

---

## App Metadata

| Key | Value |
|-----|-------|
| Title | Real Estate OS API |
| Version | 0.2.0 |
| Description | AI-платформа для агентства недвижимости |
| Runtime | Python 3.13, FastAPI async, PostgreSQL |
| Entry | `main.py` → `create_app()` → FastAPI app |
| Port | 8090 |
| DB | `postgresql+asyncpg://postgres:postgres@localhost:5432/real_estate_os` |

## Config (`config.py`)

Pydantic `BaseSettings` — reads `.env` from project root.

**Key settings:**
- `DATABASE_URL`, `DATABASE_SYNC_URL` — async/sync PostgreSQL DSNs
- `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10`
- `SECRET_KEY` (REQUIRED), `JWT_ALGORITHM=HS256`, `ACCESS_TOKEN_EXPIRE_MINUTES=1440`
- `AI_DEEPSEEK_API_KEY`, `AI_QWEN_ENDPOINT=http://localhost:8001/v1`, `AI_CHATGPT_API_KEY` (REQUIRED)
- `AI_EMBEDDING_MODEL=intfloat/multilingual-e5-small`
- `TELEGRAM_BOT_TOKEN`, `AVITO_API_KEY`, `CIAN_API_KEY`
- `LEAD_SCORE_RULE_HOT=0.80`, `WARM=0.60`, `COLD=0.30`
- `SECURITY_ENABLED=True`

## Database (`database.py`)

- Async engine: `create_async_engine` (asyncpg driver)
- Session: `async_sessionmaker` → `get_session()` dependency (auto-commit/rollback)
- Base: `DeclarativeBase`
- Mixins (`models/base.py`): `UUIDMixin` (UUID PK), `TimestampMixin` (created_at, updated_at)

---

## SQLAlchemy Models (~40+ tables)

### CORE CRM DOMAIN

**User** (`users`): role_id(FK), full_name, phone, email, telegram_id/username/chat_id, password_hash (SHA256), avatar, settings(JSONB), last_login, deleted_at. Relationships: role, deals, communications, documents, tasks.

**Role** (`roles`): name(unique), permissions(JSONB), description, is_system, deleted_at. Relationships: users.

**Client** (`clients`): type(buyer/seller), status(lead/active/inactive), full_name, phone, email, telegram, source, notes, tags(ARRAY), created_by, deleted_at. Relationships: contacts, properties, deal_participations, communications, documents, tasks.

**ClientContact** (`client_contacts`): client_id(FK), full_name, phone, email, telegram, role, notes, deleted_at.

**Property** (`properties`): property_type(apartment/house/land/commercial), status(available/sold/rented), deal_type, title, address, area_total/living(Numeric), rooms, floor, floors_total, price(Numeric 15,2,RUB), commission, owner_id(FK), photos/documents(ARRAY), notes, created_by, deleted_at. Relationships: owner, deals, documents, tasks.

**Deal** (`deals`): deal_type(purchase/rent/sale), status(negotiation/offer_made/under_review/approved/closed/cancelled), property_id(FK), title, price(Numeric 15,2,RUB), commission, deposit_amount, start_date, end_date, closing_date, source, created_by, deleted_at. Relationships: property, participants, creator, documents, communications, tasks, checkpoints, workflows.

**DealParticipant** (`deal_participants`): deal_id(FK), client_id(FK), role(buyer/seller), created_by, deleted_at.

**Document** (`documents`): document_type, status(pending/received/verified/rejected), title, file_name/path/size/hash, mime_type, client_id(FK), property_id(FK), deal_id(FK), uploaded_by(FK), expiry_date, notes, deleted_at.

**Communication** (`communications`): type(call/email/meeting/message), direction(in/out), client_id(FK), deal_id(FK), subject, content(Text), duration, assigned_to(FK), is_important, tags(ARRAY), created_by, deleted_at.

**Task** (`tasks`): title, status(pending/in_progress/completed/cancelled), priority(low/medium/high/urgent), task_type, client_id/deal_id/property_id(FKs), assigned_to/created_by/completed_by(FKs), due_date, completed_at, reminder, notes, tags(ARRAY), deleted_at.

**Lead** (`leads`): source, source_id, source_metadata(JSONB), full_name, phone, email, telegram, interest_type, property_type, budget_min/max(Numeric), locations(ARRAY), status(new/contact_made/qualifying/qualified/converted/lost/archived), score(Float 0-1), score_components(JSONB), priority(cold/warm/hot), assigned_to/qualified_by/client_id/deal_id(FKs), tags, notes, created_by, deleted_at.

**LeadEvent** (`lead_events`): lead_id(FK), event_type, from_status, to_status, from_score, change_reason, metadata(JSONB).

**Notification** (`notifications`): user_id(FK), notification_type, title, body, payload(JSONB), status(pending/sent/read), sent_at, read_at.

### DOCUMENT PIPELINE

- **DocumentChunk** — text chunks for embedding
- **Embedding** — vector embeddings (384-dim, multilingual-e5-small)
- **DocumentValidation** — validation results per document

### KNOWLEDGE GRAPH

- **GraphNode** — entity_id, node_type, title, properties(JSONB)
- **GraphEdge** — source->target, edge_type, confidence, metadata(JSONB)

### KNOWLEDGE SESSIONS

- **KnowledgeSession** — agent chat sessions
- **KnowledgeMessage** — messages within sessions

### DEAL WORKFLOW

- **DealWorkflow** — managed lifecycle (deal_id, workflow_type, current_stage, status)
- **DealStageTransition** — stage change records
- **DealCheckpoint** — required stages (deal_id, stage, checkpoint_key, label, is_required, is_completed, sort_order)
- **DealDocumentPackage** — document-to-deal requirement links
- **DealSLA** — SLA per deal type
- **DealTimelineEvent** — event timeline
- **DealPlaybook / DealPlaybookStage / DealPlaybookCheckpoint** — playbook definitions
- **DealRiskAssessment** — risk scoring
- **DealHealthSnapshot** — periodic health checks
- **DealAction** — actions on deals
- **DealOperationsAudit** — audit trail

### REQUIREMENTS & REGULATIONS

- **DocumentRequirement** — required docs per deal_type (unique: deal_type+document_type)
- **Regulation** — regulatory acts (title, source, trust_level, version, effective_from/to, content, hash, category)
- **RegulationVersion** — versioned snapshots
- **RegulationSource** — source definitions
- **RegulationChangeEvent** — detected changes
- **RegulationSyncLog** — sync history
- **RegulationImpact** — impact analysis
- **RegulationRequirementMapping** — reg-to-req mapping

### COMPLIANCE & SETTINGS

- **ComplianceAudit** — audit records
- **PlatformSetting** — key-value settings

### AI / BUDGET / AUDIT

- **AIQueryLog** — AI call audit
- **AgentToolCall** — agent tool execution records
- **BudgetUsage** — per-user AI budget
- **SystemJob** — background job scheduling

### ANALYTICS

- **AnalyticsSnapshot** — periodic data snapshots
- **AnalyticsAlert** — predefined alerts
- **PredictionResult** — ML predictions

### STAKEHOLDERS

- **Stakeholder** — external stakeholders

### ACCOUNTING (`accounting.*` schema via raw SQL + migrations 026-034)

Tables: `accounting_event`, `accounting_decision`, `decision_explanation`, `accounting_batch`, `accounting_journal`, `accounting_entry`, `ledger_account`, `ledger_entry`, `ledger_balance`, `tax_calculation`, `tax_return`, `tax_period`, `financial_report`, `report_section`, `reconciliation_run`, `reconciliation_item`, `control_action`, `control_log`.

---

## Pydantic Schemas (`schemas/`)

- **BaseSchema**: `from_attributes=True`
- **BaseResponse**: id(UUID), created_at, updated_at
- **PaginationParams**: page(int=1), page_size(int=50)
- **PaginatedResponse**: items(list), total, page, page_size, total_pages
- Per entity: `{Entity}Create`, `{Entity}Update`, `{Entity}Response` for Lead/Client/Property/Deal/Task
- Note: Some routes use inline Pydantic models instead of shared schemas (clients, deals, properties via asyncpg)

---

## API Routes (all under `/api/v1` prefix)

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Status, version, migration_head |
| GET | /health/live | Liveness probe |
| GET | /health/ready | Readiness probe (db) |
| GET | /version | App version info |

### Clients (direct asyncpg)
| Method | Path | Description |
|--------|------|-------------|
| GET | /clients | List (paginated, soft-delete filter) |
| GET | /clients/{id} | Get by ID |

### Deals (direct asyncpg)
| Method | Path | Description |
|--------|------|-------------|
| GET | /deals | List (paginated) |
| POST | /deals | Create (enriches from document profile) |
| GET | /deals/{id} | Get by ID |

### Properties (direct asyncpg)
| Method | Path | Description |
|--------|------|-------------|
| GET | /properties | List (paginated) |
| GET | /properties/search | Search by title/address (ILIKE) |
| GET | /properties/{id} | Get by ID |

### Auth (direct asyncpg)
| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/login | SHA256 pwd + JWT (HS256, 24h) |

### Users (SQLAlchemy)
| Method | Path | Description |
|--------|------|-------------|
| GET | /users | List all |
| POST | /users | Create |
| GET | /users/by-telegram/{id} | Find by telegram |
| GET | /users/{id} | Get by ID |

### Leads (SQLAlchemy)
| Method | Path | Description |
|--------|------|-------------|
| POST | /leads | Create (duplicate detection) |
| GET | /leads | List |
| GET | /leads/{id} | Get |
| PATCH | /leads/{id} | Update |
| DELETE | /leads/{id} | Archive (soft delete) |
| POST | /leads/{id}/assign | Assign to user |
| POST | /leads/{id}/score | Set score (0-1) |
| POST | /leads/{id}/qualify | Qualify |
| POST | /leads/{id}/close | Close (lost) |
| POST | /leads/{id}/convert | Convert to client + optional deal |

### Document Intake (sync psycopg2)
Lifecycle: UPLOADED -> VALIDATED -> ACCEPTED -> PROCESSING -> ANALYZED -> READY -> ROUTED -> ARCHIVED

| Method | Path | Description |
|--------|------|-------------|
| POST | /documents/upload | Upload file |
| GET | /documents/{id} | Get details |
| GET | /documents/{id}/status | Status + allowed transitions |
| POST | /documents/{id}/transition | Transition state |
| GET | /documents | List (filtered by status) |

### Document Processing (sync psycopg2)
Pipeline steps: OCR -> Classification -> Extraction -> Knowledge

| Method | Path | Description |
|--------|------|-------------|
| POST | /processing/pipelines/start/{doc_id} | Start pipeline |
| GET | /processing/pipelines/{id} | Status + steps |
| POST | /processing/pipelines/{id}/retry | Retry failed |

### Document-to-Deal Promotion
| Method | Path | Description |
|--------|------|-------------|
| POST | /documents/{id}/promote-to-deal | Create deal from OCR doc (confidence-gated: >=0.90 auto, >=0.70 review) |
| POST | /documents/{id}/bind-to-deal/{deal_id} | Bind to existing deal |
| GET | /deals/{id}/requirements | List required docs |
| GET | /deals/{id}/timeline | Timeline events |

### Agent Runtime
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/agent/ask | Ask AI agent (rate-limited) |
| GET | /api/v1/agent/tools | List agent tools |

Agent tools: check_deal_completeness, validate_document_package, get_regulation, search_client, search_property, search_deal

### Knowledge
| Method | Path | Description |
|--------|------|-------------|
| POST | /knowledge/search | Semantic search (documents/clients/properties/all) |
| GET | /knowledge/graph/entity/{id} | Entity graph |
| POST | /knowledge/rebuild | Rebuild knowledge graph |
| GET | /knowledge/stats | Graph stats |

Additional knowledge routers: explorer, timeline, diff, search, traversal, consistency, audit, trust, governance, recovery.

### System
| Path | Tags |
|------|------|
| /notifications | Notifications |
| /jobs | System Jobs |
| /platform | Platform Settings |
| /obligations | Obligations (payment calendar) |
| /companies | Companies |

### Compliance Rules Catalog
| Method | Path | Description |
|--------|------|-------------|
| POST/GET | /rules | CRUD |
| GET/PUT | /rules/{code} | Get/Update |
| POST | /rules/{code}/publish | Publish version |
| POST | /rules/{code}/deprecate | Deprecate |
| GET | /rules/{code}/versions | Version history |
| GET/POST/DELETE | /organizations/{org_id}/overrides | Override management |
| GET | /organizations/{org_id}/applicable-rules | Resolve rules |

### Accounting
| Method | Path | Description |
|--------|------|-------------|
| GET | /accounting/events | List with filters |
| GET | /accounting/events/{id} | Get event details |
| GET | /accounting/events/{id}/decision | Active decision |
| GET | /accounting/events/{id}/explanations | Decision explanations |
| GET | /accounting/batches/{id} | Batch + events |
| POST | /accounting/replay | Recalculate |
| GET | /accounting/dlq | Dead letter queue |
| POST | /accounting/dlq/{id}/reprocess | Reprocess DLQ'd |
| GET | /accounting/metrics | Pipeline metrics |

Additional accounting routers: Ledger (chart, posting, entries), Tax (calculations, returns, optimization), Reports (generation, audit, submission), Reconciliation (runs, items), Control (actions, logs).

---

## Services (`services/`)

### Core Services
- **BaseService** — delegates CRUD to GenericRepository
- **LeadService** — lifecycle mgmt, ADR-0013 state machine, scoring, conversion->client, merge, events
- **ClientService** — create/update/merge/archive, duplicate detection, entity reassignment
- **DealService** — create (with participants), status transitions, attach property, participants
- **PropertyService**, **TaskService**, **CommunicationService**, **UserService**

### Document & Pipeline
- **DocumentLifecycleService** — intake + state machine (sync psycopg2)
- **PipelineOrchestrator** — sequential step execution (OCR->Classification->Extraction->Knowledge)
- **DocumentPackageService**, **WorkflowService**

### AI
- **AI Router** — TaskType->provider routing with fallback chain (DeepSeek primary, OpenAI fallback)
- **ProviderRegistry** — primary/fallback/custom providers
- **AgentRuntime** — IntentClassifier -> ToolPlanner -> ToolExecutor
- **RateLimiter** (10/min, 100/hour), **CostTracker** (per-user budget)
- **AgentTools**: check_deal_completeness, validate_document_package, get_regulation, search_client/property/deal

### Knowledge
- **KnowledgeAssemblyService** — context building, graph expansion, token counting
- **KnowledgeMemoryService** — memory cleanup
- **KnowledgeSecurityService** — XML injection detection, sanitization
- **GraphLifecycleService** — CRM->Graph sync
- **KnowledgeSearchService** — unified search

### Compliance & Regulation
- **RuleCatalogService** — rule lifecycle management
- **RulesResolver** — org+date rule resolution
- **RegulationService**, **RegulationParserService**, **RegulationSyncService**
- **ImpactAnalysisService**, **RiskAssessmentService**

### Accounting
- Services in `services/accounting/`: closing, posting, reconciliation, reporting, mapper
- Orchestrator: event dispatching, job scheduling, workers (decision, recognition, replay)
- Ledger posting engine with rules (bank_transfer, client_payment, expense_payment, etc.)
- Tax: calculation, optimization, period management

### System
- **SystemJobService**, **NotificationService**, **AgentToolAuditService**
- **AnalyticsService** (snapshots, alerts, predictions)
- **AutonomousServices**, **ExecutiveServices**

---

## Repositories (`repositories/`)

All extend `GenericRepository[T]` (async CRUD + soft delete):
- UserRepository, ClientRepository, PropertyRepository, DealRepository
- LeadRepository, TaskRepository, CommunicationRepository, DocumentRepository
- NotificationRepository, DocumentRequirementRepository, DealCheckpointRepository
- RegulationRepository, SystemJobRepository
- KnowledgeSessionRepository, KnowledgeMessageRepository
- AgentToolCallRepository, AIQueryLogRepository, BudgetUsageRepository

---

## Core Infrastructure (`core/`)

### Domain Events
- **DomainEventBus** — synchronous singleton event bus
- Events: client.created/updated/deleted, property.*, deal.*, document.created/deleted, lead.converted/merged
- Handlers: graph_sync_handler, embedding_sync_handler, search_index_handler, audit_handler

### Middleware
- CORSMiddleware (allow all origins)
- RequestContextMiddleware (user_id, correlation_id)

### Other
- structlog structured logging
- Global error handlers
- DatabaseHealthCheck, HealthService
- Background scheduler

---

## AI Layer (`ai/`)

- **Providers**: DeepSeekProvider (primary), OpenAIProvider (fallback), Qwen endpoint at localhost:8001/v1
- **Router**: TaskType routing with timeout (65s), fallback chain, budget enforcement
- **Classifier**: Document type detection
- **Extraction**: Contract fields, parties, financial terms, dates, references, property info
- **Embeddings**: 384-dim, multilingual-e5-small
- **Graph**: KnowledgeGraphBuilder
- **Search**: Unified semantic search
- **Metrics**: Prometheus counters (budget rejections, provider failures, rate limit hits)

---

## Alembic Migrations (`migrations/versions/`)

35 migrations total, current head: `034_control_plane_schema`

Organized by domain:
- **002-008**: Core foundation (leads, notifications, system_jobs, knowledge, AI logs, budgets, memory)
- **009-017**: Deal workflow (checkpoints, requirements, regulations, agent tools, risk, compliance, audit)
- **018-025**: Hardening (partitioning, constraints, FK lifecycle, soft delete consistency)
- **026-034**: Accounting suite (schema, constraints, indexes, ledger, tax, reporting, reconciliation, control plane)

Migration engine: Async via `run_async_migrations()` in `migrations/env.py`

---

## Key Architecture Notes

1. **Three DB access patterns coexist**:
   - Direct `asyncpg` in clients/deals/properties/auth/obligations/promote_to_deal routes (raw SQL)
   - SQLAlchemy async in leads/users/tasks/knowledge routes (via `get_session()`)
   - Sync `psycopg2` in document_lifecycle and processing modules (Product Layer)

2. **Document pipeline is Product Layer** (not Platform): uses its own `document_intake` table + sync psycopg2

3. **Knowledge Graph syncs from CRM** via DomainEventBus (graph_sync_handler)

4. **Soft delete pattern**: all core entities have `deleted_at`; GenericRepository filters by default

5. **State machines**: Lead (8 states via ADR-0013), Deal (6 states), Document (8 lifecycle states), Pipeline (5 states)

6. **Two accounting models**: `services/accounting/` (service layer) + `accounting/` (full DDD with API routes)

7. **Compliance module** has its own DDD: domain -> application -> infrastructure -> api

8. **Agent Runtime** is loaded lazily at first `/ask` request

9. **Static system user UUID**: `5055acf6-e7f2-4b9a-82f7-f19eba6caff6` (fallback created_by in document->deal pipeline)

10. **Security**: SHA256 password hashing, JWT (HS256, 24h), configurable security layer (XML sanitize, CDATA sanitize), soft deletes everywhere
