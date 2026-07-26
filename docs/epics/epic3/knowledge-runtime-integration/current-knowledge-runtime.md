# Knowledge Runtime Integration — Phase 0 Discovery

> **Date:** 2026-07-26  
> **Context:** Epic 3 завершён: Stream 0 (Document Lifecycle), Stream 3 (Business Events), Deal Context Resolution.  
> **Task:** Исследовать текущее состояние Knowledge Graph, Embedding Pipeline, Search Runtime, Event Contract, Consumer Architecture.

---

## 1. Knowledge Graph

### 1.1 SQLAlchemy Models

#### `GraphNode` — `backend/models/graph_node.py` (строки 16-27)
```python
class GraphNode(UUIDMixin, Base):  # tablename = "graph_nodes"
```
| Поле | Тип | Nullable | Индекс |
|------|-----|----------|--------|
| `node_type` | String(50) | NO | YES |
| `entity_id` | UUID | NO | YES |
| `source_entity_type` | String(50) | YES | — (входит в составной) |
| `source_entity_id` | UUID | YES | YES |
| `title` | String(255) | NO | — |
| `meta` (metadata) | JSONB | YES | — |
| `deleted_at` | DateTime(tz) | YES | — |
| `created_at` | DateTime(tz) | NO (server_default) | — |
| `updated_at` | DateTime(tz) | NO (server_default+onupdate) | — |

**Факты:**
- Уникальный составной индекс `ix_graph_nodes_type_entity` на `(node_type, entity_id)` — создан в миграции 005, но **НЕ объявлен** в модели `GraphNode.__table_args__`
- `source_entity_type` + `source_entity_id` добавлены в миграции 016 для referential integrity
- Soft delete через `deleted_at` (миграция 016)
- `UUIDMixin` добавляет поле `id` (UUID, PK, server_default=gen_random_uuid())

#### `GraphEdge` — `backend/models/graph_edge.py` (строки 16-25)
```python
class GraphEdge(UUIDMixin, Base):  # tablename = "graph_edges"
```
| Поле | Тип | Nullable | Индекс |
|------|-----|----------|--------|
| `source_node_id` | UUID (FK→graph_nodes.id CASCADE) | NO | YES |
| `target_node_id` | UUID (FK→graph_nodes.id CASCADE) | NO | YES |
| `edge_type` | String(50) | NO | YES |
| `confidence` | Float | NO (default=1.0) | — |
| `meta` (metadata) | JSONB | YES | — |
| `deleted_at` | DateTime(tz) | YES | — |
| `created_at` | DateTime(tz) | NO (server_default) | — |

**Факты:**
- Составные индексы: `ix_graph_edges_source_type(source_node_id, edge_type)`, `ix_graph_edges_target_type(target_node_id, edge_type)`
- Каскадное удаление при удалении узла
- Soft delete для edges также каскадируется при `soft_delete_node()`

### 1.2 GraphLifecycleService — `backend/services/graph_lifecycle_service.py`

**Методы:**
| Метод | Назначение |
|-------|-----------|
| `create_node(node_type, entity_id, title, source_entity_type, source_entity_id, metadata)` | Создать узел с source_entity tracking |
| `soft_delete_node(node_id)` | Мягкое удаление узла + каскадное удаление его edges |
| `restore_node(node_id)` | Восстановить мягко удалённый узел (edges не восстанавливаются) |
| `sync_entity(entity_type, entity_id, title, metadata)` | **Основной метод**: найти по `source_entity_type + source_entity_id` → создать или обновить |

**Факты:**
- `sync_entity()` — единственный метод, используемый извне (через GraphSyncConsumer)
- Не принимает `GraphLifecycleService(session)` — принимает session в конструкторе (строка 22-23)
- **НО**: в GraphSyncConsumer создаётся `GraphLifecycleService()` **без session** (строка 52) — это баг или сессия не нужна для sync_entity? (sync_entity использует self.session напрямую)
- Не использует Event Bus на выходе — нет emit после sync

### 1.3 KnowledgeGraphBuilder — `backend/ai/graph/__init__.py`

**Факты:**
- Старый batch-билдер для полной перестройки графа из CRM-сущностей
- Использует `pg_insert(...).on_conflict_do_nothing(index_elements=["node_type", "entity_id"])`
- Идемпотентен — перезапуск не создаёт дубликатов
- Вызывается через `POST /api/v1/knowledge/rebuild`
- Node types: client, property, deal, document, lead, communication, organization
- Edge types: owns, participates_in, related_to, generated_from, refers_to, converts_to
- **Gap:** не использует `source_entity_type/source_entity_id` поля; использует только `node_type + entity_id`
- **Gap:** не синхронизируется с GraphSyncConsumer — существует параллельно

### 1.4 GraphSyncConsumer — `backend/infrastructure/consumers/graph_sync_consumer.py`

**Факты:**
- Наследует `BaseConsumer` — встроенная идемпотентность через `ConsumerStateRepository`
- `consumer_name = "graph_sync"`
- `_process(event)`:
  1. Извлекает `entity_type = event.aggregate_type`, `entity_id = event.aggregate_id`
  2. Берёт `event.event_type.split(".")[0]` как title
  3. Создаёт `GraphLifecycleService()` — **без аргументов!!** (баг — session=None)
  4. Вызывает `svc.sync_entity(entity_type, entity_id_uuid, source_label)`
- **Gap:** Нет обработки payload — передаётся только entity_type+entity_id+title без meta/data
- **Gap:** Нет триггера на embedding pipeline — только sync_entity в граф
- **Gap:** Синхронизирует только навигационные поля, не content
- **Gap:** Документация говорит о backward compatibility со старым `graph_sync_handler`, но старый handler удалён из `event_handlers.py`

---

## 2. Embedding Pipeline

### 2.1 Models

#### `Embedding` — `backend/models/embedding.py` (строки 15-27)
```python
class Embedding(UUIDMixin, Base):  # tablename = "embeddings"
```
| Поле | Тип | Nullable |
|------|-----|----------|
| `entity_type` | String(100) | NO (index) |
| `entity_id` | UUID | NO (index) |
| `chunk_id` | UUID | YES |
| `model_name` | String(100) | NO |
| `embedding` | Vector(384) | NO (pgvector) |
| `content_hash` | String(64) | NO (UNIQUE) |
| `meta` (metadata) | JSONB | YES |
| `token_count` | Integer | YES |
| `created_at` | DateTime(tz) | NO (server_default) |

**Индексы (миграция 005):**
- `ix_embeddings_hnsw` — HNSW index on embedding (vector_cosine_ops)
- `ix_embeddings_ivfflat` — IVFFlat index on embedding (vector_cosine_ops)
- Unique on `content_hash` (глобальная дедупликация контента)

#### `DocumentChunk` — `backend/models/document_chunk.py` (строки 14-22)
```python
class DocumentChunk(UUIDMixin, Base):  # tablename = "document_chunks"
```
| Поле | Тип | Nullable |
|------|-----|----------|
| `document_id` | UUID (FK→documents.id CASCADE) | NO (index) |
| `chunk_index` | Integer | NO |
| `content` | Text | NO |
| `token_count` | Integer | YES |
| `meta` (metadata) | JSONB | YES |
| `created_at` | DateTime(tz) | NO (server_default) |

**Индекс:** `ix_document_chunks_doc_chunk(document_id, chunk_index)` — unique

### 2.2 EmbeddingPipeline — `backend/ai/embeddings/__init__.py`

**Факты:**
- **Model:** `intfloat/multilingual-e5-small` (384 dim) через `sentence-transformers`
- **Fallback:** если sentence-transformers не установлен → `logger.warning + return 0` (stub mode)
- **Методы:**
  - `embed_chunks(document_id)` — встраивает все chunks документа с дедупликацией по `content_hash`
  - `embed_text(text, entity_type, entity_id)` — встраивает произвольный текст
- **Dedup:** двухуровневая — проверяет `existing hashes` for this document (by chunk_id) + global hashes (limit 10000)
- **Normalization:** `model.encode(text, normalize_embeddings=True)`
- **Gap:** `embed_chunks` никогда не вызывается — нет триггера от GraphSyncConsumer или DocumentLifecycle
- **Gap:** chunk extraction (разбиение документа на chunks) — не обнаружен код, chunks создаются вне этого pipeline
- **Gap:** EmbeddingPipeline не thread-safe (разделяемый `self._model`)

### 2.3 Чейн вызовов

```
Document ready
  → DomainEventBus.emit("document.ready")
    → EventAdapter.to_integration() → Outbox
      → Publisher._poll_once()
        → GraphSyncConsumer._process() → GraphLifecycleService.sync_entity()
        → DealContextResolutionConsumer._process() → DealContextResolver.resolve()
❌ Нет → EmbeddingPipeline.embed_chunks()
❌ Нет → Search index update
```

**Ключевой gap:** Embedding pipeline не подключён к Event Backbone. Никто не вызывает `embed_chunks()`.

---

## 3. Search Runtime

### 3.1 Два Search API (CONFLICT)

#### API A (WIRED) — `backend/api/routes/knowledge.py` + `backend/ai/search/__init__.py`
- **Endpoint:** `POST /api/v1/knowledge/search` (legacy)
- **Router:** `knowledge_router` — подключён в `router.py` (строка 42)
- **Service:** `KnowledgeSearchService` в `backend/ai/search/__init__.py`
- **Entity types:** documents, clients, properties, everything (по entity_type filter)
- **Hybrid search:**
  1. Full-text: PostgreSQL `to_tsvector('russian')` + `plainto_tsquery('russian')` на `DocumentChunk.content`
  2. Vector: `Embedding.embedding.cosine_distance(query_vec)` via pgvector
  3. Merge: 0.3 × FTS + 0.7 × vector → hybrid score
- **Model:** `multilingual-e5-small` через `sentence-transformers` (inline, no caching)
- **Async:** использует async SQLAlchemy session

#### API B (DEAD CODE) — `backend/api/routes/knowledge_search.py`
- **Endpoint:** `GET /knowledge/search` (prefix)
- **Router:** **НЕ подключён** в `router.py` → dead code
- **Service:** `KnowledgeSearchService(dsn)` из `application/capabilities/search_service.py`
- **Тип:** Deterministic structured search по `knowledge_revisions` таблице
- **Параметры:** source_document_id, reason_contains, created_by, created_after/before, revision_number range, cursor pagination
- **Model:** не AI — SQL-запрос к PostgreSQL direct через psycopg2

### 3.2 Traversal API (DEAD CODE) — `backend/api/routes/knowledge_traversal.py`
- **Endpoint:** `GET /knowledge/traversal` (prefix)
- **Router:** НЕ подключён в `router.py` → dead code
- **Service:** `KnowledgeGraphTraversalService` из `application/capabilities/traversal_service.py`
- **Тип:** 1-hop traversal через Materialized projections

### 3.3 Explorer API (WIRED) — `backend/api/routes/knowledge_explorer.py`
- **Endpoints:** 
  - `GET /knowledge/revisions` — список
  - `GET /knowledge/revisions/{id}` — детали
  - `GET /knowledge/revisions/{id}/graph` — KnowledgeSnapshot graph
  - `GET /knowledge/revisions/{id}/provenance` — provenance
  - `GET /knowledge/revisions/{id}/explanation` — explanation
- **Router:** `explorer_router` — подключён в `router.py` (строка 43)
- **Source:** `KnowledgeRuntimeIntegrator.revision_repository` + direct psycopg2 queries

### 3.4 Health / Stats — `backend/api/routes/knowledge.py`
- `GET /api/v1/knowledge/stats` — counts: nodes, edges, embeddings, chunks

### 3.5 Key Findings
- **Full-text search** — есть (tsvector). **Vector search** — есть (pgvector cosine). Но нет unified hybrid реранкера.
- **Индексирование:** нет background задачи для async index update. Embedding pipeline живёт отдельно от событий.
- **Gap:** `document.ready` → `EmbeddingPipeline.embed_chunks()` не вызывается
- **Gap:** Два KnowledgeSearchService класса с одинаковым именем в разных модулях — путаница

---

## 4. Event Contract

### 4.1 Domain Event Types — `backend/core/domain_events.py` (строки 71-91)

| Константа | Значение | Описание |
|-----------|----------|----------|
| `EVENT_CLIENT_CREATED` | `client.created` | Клиент создан |
| `EVENT_CLIENT_UPDATED` | `client.updated` | Клиент изменён |
| `EVENT_CLIENT_DELETED` | `client.deleted` | Клиент удалён |
| `EVENT_PROPERTY_CREATED` | `property.created` | Объект создан |
| `EVENT_PROPERTY_UPDATED` | `property.updated` | Объект изменён |
| `EVENT_PROPERTY_DELETED` | `property.deleted` | Объект удалён |
| `EVENT_DEAL_CREATED` | `deal.created` | Сделка создана |
| `EVENT_DEAL_UPDATED` | `deal.updated` | Сделка изменена |
| `EVENT_DEAL_DELETED` | `deal.deleted` | Сделка удалена |
| `EVENT_DOCUMENT_CREATED` | `document.created` | Документ создан |
| `EVENT_DOCUMENT_DELETED` | `document.deleted` | Документ удалён |
| **`EVENT_DOCUMENT_READY`** | **`document.ready`** | **Документ готов (полный ContractProfile JSONB)** |
| `EVENT_LEAD_CONVERTED` | `lead.converted` | Лид конвертирован |
| `EVENT_LEAD_MERGED` | `lead.merged` | Лиды объединены |

### 4.2 IntegrationEvent Envelope — `backend/core/integration_event.py`

```python
@dataclass(frozen=True)
class IntegrationEvent:
    event_id: UUID          # stable across retries
    event_type: str          # e.g. "document.ready"
    aggregate_type: str      # e.g. "Document"
    aggregate_id: str        # stable business entity ID
    occurred_at: datetime
    version: int = 1
    payload: dict            # domain payload
    metadata: dict | None
```

**EventAdapter** (строки 67-116): DomainEvent → IntegrationEvent
- `aggregate_type` = `domain_event.entity_type.capitalize()` (если не передан override)
- `aggregate_id` = `str(domain_event.entity_id)`
- `event_id` = `uuid4()` — generated fresh on conversion
- metadata: schema_version=1, producer="domain", correlation_id

### 4.3 Consumer Registration — `backend/main.py` (строки 75-96)

**Publisher регистрирует два consumer'а:**

```python
EVENT_TYPES = ["document.ready", "document.created", "document.deleted",
               "client.created", "client.updated", "client.deleted",
               "property.created", "property.updated", "property.deleted",
               "deal.created", "deal.updated", "deal.deleted",
               "lead.converted", "lead.merged"]

for et in EVENT_TYPES:
    publisher.register_consumer(et, graph_sync.consume)  # GraphSync на ВСЕ типы

publisher.register_consumer("document.ready", deal_context_resolution.consume)  # DCR только на document.ready
```

**Для `document.ready` — ДВА consumer'а:** GraphSyncConsumer + DealContextResolutionConsumer

### 4.4 Old DomainEventBus Handlers — `backend/core/event_handlers.py`

**Текущие handlers (все — stub):**
| Handler | Действие |
|---------|----------|
| `embedding_sync_handler(event)` | **Stub** — только `logger.info("embedding_sync", ...)` |
| `search_index_handler(event)` | **Stub** — только `logger.info("search_index_sync", ...)` |
| `audit_handler(event)` | **Stub** — только `logger.info("domain_audit", ...)` |

**Registration (через `event_registry.py`):**
- `client.*` + `property.*` + `deal.*` → только `audit_handler`
- `document.*` → `[embedding_sync_handler, search_index_handler, audit_handler]`
- `lead.*` → только `audit_handler`
- **Legacy `graph_sync_handler` удалён** (мигрирован в Event Backbone)

**Gap:** `embedding_sync_handler` и `search_index_handler` — пустые заглушки. Никакой реальной логики.

### 4.5 DocumentReady Payload

DealContextResolutionConsumer ожидает в `event.payload`:
```json
{
  "document_id": "uuid",
  "profile": { /* ContractProfile JSONB */ }
}
```
**Gap:** Нет формальной схемы/валидации payload для document.ready. Что именно содержит profile — не зафиксировано в коде consumer.

---

## 5. Consumer Architecture

### 5.1 BaseConsumer — `backend/infrastructure/consumer_base.py`

**Protocol** `EventConsumer`:
```python
async def consume(self, event: IntegrationEvent) -> ConsumerResult
```

**`ConsumerResult`** (frozen dataclass):
| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Успех |
| `error` | str\|None | Сообщение об ошибке |
| `retryable` | bool | Если False → poison message → dead letter (default True) |

**`BaseConsumer` (ABC):**
```
consume(event):
  1. Dedup check → ConsumerStateRepository.is_processed(consumer_name, event_id)
     → skip if already processed
  2. _process(event) ← abstract, реализуется subclass'ом
  3. ConsumerStateRepository.mark_processed(consumer_name, event_id)
  4. На ошибку → return ConsumerResult(success=False, retryable=True)
```

### 5.2 ConsumerStateRepository — `backend/repositories/consumer_state_repository.py`

- **Table:** `consumer_processed_events`
- **Columns:** consumer_name (PK), event_id (PK), processed_at
- **Dedup SQL:** `INSERT ... ON CONFLICT (consumer_name, event_id) DO NOTHING`
- **Sync psycopg2:** использует синхронный psycopg2 (не async) — может блокировать event loop
- **No TTL/expiry:** consumer_processed_events растёт бесконечно (нет очистки)

### 5.3 EventPublisher — `backend/infrastructure/event_publisher.py`

**Конфигурация (main.py):**
| Параметр | Значение |
|----------|----------|
| `poll_interval` | 1.0s |
| `batch_size` | 50 |
| `max_retries` | 3 |
| `backoff_base` | 1.0s (→ 1s, 2s, 4s) |

**Lifecycle:**
1. `start()` — background asyncio task (lifespan)
2. `_poll_once()` — fetch pending → process → fetch failed (with backoff) → retry
3. `stop()` — drain in-flight events (5s timeout)

**At-least-once:** event marked `published` only after ALL consumers confirm success
**Dead letter:** после max_retries → status='dead' → never re-polled

### 5.4 Outbox — `backend/models/event_outbox.py`

**Table:** `event_outbox`
| Поле | Тип |
|------|-----|
| id | UUID PK |
| event_type | VARCHAR(100) |
| aggregate_type | VARCHAR(50) |
| aggregate_id | VARCHAR(255) |
| payload | JSONB |
| metadata | JSONB |
| created_at | TIMESTAMPTZ |
| published_at | TIMESTAMPTZ (nullable) |
| attempts | INTEGER (default 0) |
| last_error | TEXT (nullable) |
| status | VARCHAR(20): pending|published|failed|dead |

**Indexes:**
- `idx_outbox_status_created` — partial WHERE status='pending'
- `idx_outbox_status_attempts` — partial WHERE status='failed'

### 5.5 GraphSyncConsumer — Bug Analysis

```python
class GraphSyncConsumer(BaseConsumer):
    async def _process(self, event: IntegrationEvent) -> None:
        from backend.services.graph_lifecycle_service import GraphLifecycleService
        # ...
        svc = GraphLifecycleService()  # ❌ NO session passed!
        # ...
        await svc.sync_entity(entity_type, entity_id_uuid, source_label)
        # sync_entity does: self.session.execute(...) ← AttributeError on None.session
```

**Это баг:** `GraphLifecycleService.__init__(self, session)` требует session, но GraphSyncConsumer создаёт без аргументов. `sync_entity()` вызовет `self.session.execute()` → `AttributeError: 'NoneType' object has no attribute 'execute'`.

### 5.6 BusinessEvents Table

BusinessEvents (`business_events`, миграция 035) — append-only event log:
- Хранит все IntegrationEvent для replay
- Индексы: aggregate, event_type, occurred_at
- **Gap:** не подключён к Publisher — Publisher не пишет в business_events (только в outbox)

---

## 6. Knowledge Runtime Integrator

### 6.1 KnowlegeRuntimeIntegrator — `services/accounting_binding/application/knowledge_persistence/integrator.py`

**Факты:**
- Бутстрапится в `main.py` (строки 106-130) как `app.state.integrator`
- Использует `PostgreSQLKnowledgeRevisionRepository` + `PostgreSQLProjectionStore`
- Хранит `ProjectionRegistry` с 4-мя билдерами: Entity, Agreement, Graph, Provenance
- `BuildPlan`: ENTITY → AGREEMENT → GRAPH → PROVENANCE (ordered steps)
- **Метод `integrate()` — НИКОГДА НЕ ВЫЗЫВАЕТСЯ** в production коде

### 6.2 Capabilities Layer

| Capability | Router | API path | Status |
|-----------|--------|----------|--------|
| Knowledge Explorer | `explorer_router` | `/api/v1/knowledge/revisions/...` | **WIRED** |
| Knowledge Search | — | `/knowledge/search` (prefix) | **DEAD CODE** |
| Knowledge Traversal | — | `/knowledge/traversal` (prefix) | **DEAD CODE** |

Knowledge Search и Knowledge Traversal API определены как Capabilities (см. `backend/api/routes/knowledge_search.py` и `knowledge_traversal.py`) **но не импортированы** в `router.py`.

---

## 7. Key Findings

### 7.1 Critical Bugs

1. **GraphSyncConsumer не работает** — создаёт `GraphLifecycleService()` без session, `sync_entity()` упадёт с AttributeError при попытке `self.session.execute()`. **Line:** `graph_sync_consumer.py:52`.
2. **KnowledgeRuntimeIntegrator.integrate() — dead code** — бутстрапится на старте, но никогда не вызывается. Не подключён ни к Event Backbone, ни к Uploads.

### 7.2 Architectural Gaps

3. **Embedding pipeline отключён** — `EmbeddingPipeline.embed_chunks()` никогда не вызывается после document lifecycle. `embedding_sync_handler` и `search_index_handler` — заглушки.
4. **Нет async index update** — нет background-задачи для embedding/indexing после событий. Всё синхронно и не подключено.
5. **Две параллельные search системы:** legacy (`POST /api/v1/knowledge/search` с hybrid BM25+vector) и новая Capability (dead code).
6. **Два параллельных graph механизма:** `GraphLifecycleService.sync_entity()` (через Event Backbone) и `KnowledgeGraphBuilder.build_full()` (batch rebuild).
7. **ConsumerStateRepository — sync psycopg2:** использует синхронные вызовы в async контексте (может блокировать event loop).
8. **Нет очистки consumer_processed_events** — таблица растёт бесконечно.

### 7.3 Design Issues

9. **document.ready — dual handling:** GraphSyncConsumer (all events) + DealContextResolutionConsumer (только document.ready). Оба имеют свой dedup. При ошибке в одном — весь batch помечается failed.
10. **GraphNode model — missing __table_args__:** unique constraint `(node_type, entity_id)` существует в миграции, но не объявлен в модели через `__table_args__` + `UniqueConstraint`.
11. **Knowledge Search class collision:** два класса с именем `KnowledgeSearchService` — один в `backend/ai/search/__init__.py`, другой в `application/capabilities/search_service.py`.
12. **DocumentReady payload — неспецифицирован:** нет формальной схемы, что содержит `profile` в payload.

### 7.4 Migration Status

13. **Old graph_sync_handler удалён** из `event_handlers.py` (согласно docstring). Тест `test_freshness.py` (line 137) всё ещё импортирует `from backend.core.event_handlers import graph_sync_handler` — это падающий импорт.

---

## 8. Recommendation for Phase 1

### 8.1 Critical (Blockers)

| # | Задача | Причина |
|---|--------|---------|
| 1 | Исправить GraphSyncConsumer: передать async SQLAlchemy session | Баг — consumer не работает |
| 2 | Подключить EmbeddingPipeline к document.ready событию | Core pipeline отключён |

### 8.2 High Priority

| # | Задача | Причина |
|---|--------|---------|
| 3 | Создать async репозиторий хранения embeddings (вместо sync psycopg2) | Event loop blocking |
| 4 | Удалить dead code Capabilities (knowledge_search.py, knowledge_traversal.py) или подключить их в router | Артефакты архитектуры |
| 5 | Задокументировать `document.ready` payload schema | Отсутствие спецификации |

### 8.3 Medium Priority

| # | Задача | Причина |
|---|--------|---------|
| 6 | Объединить два KnowledgeSearchService | Code clarity |
| 7 | Убрать `embedding_sync_handler`/`search_index_handler` stub или реализовать | Пустые обработчики |
| 8 | Подключить `business_events` log к Publisher | Append-only log не используется |
| 9 | Fix test_freshness.py (dead import) | Падающий тест |

### 8.4 Low Priority

| # | Задача | Причина |
|---|--------|---------|
| 10 | TTL-based cleanup для `consumer_processed_events` | Бесконечный рост |
| 11 | Async background indexing task | Нет индексирования |
| 12 | KnowledgeRuntimeIntegrator.integrate() wiring | Dead orchestrator |

---

*Generated by Phase 0 Discovery on 2026-07-26*
