# Current Event Backbone — Phase 0 Discovery (Stream 3)

> **Phase 0 — Architecture Discovery | Event Backbone Discovery.**
> No code changes. Honest snapshot of the existing Event Backbone as of July 2026.
> Создан: 2026-07-26 | Stream 3 — Business Events | Epic 3 — Accounting Compliance & Reporting

---

## 1. Current State — Domain Events

### 1.1 DomainEvent dataclass

**Файл:** `backend/core/domain_events.py`

```python
@dataclass
class DomainEvent:
    """Базовый доменный event."""
    event_type: str
    entity_type: str
    entity_id: UUID
    actor_id: str = "system"
    correlation_id: str = ""
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

**Примечание:** `DomainEvent` — mutable dataclass (не `frozen=True`). Это **не** будет совместимо с append-only моделью Stream 3, где все события должны быть frozen.

### 1.2 Существующие event_type константы

| Константа | event_type | entity_type | Где эмитится | Реально эмитится? |
|-----------|------------|-------------|--------------|:---:|
| `EVENT_CLIENT_CREATED` | `client.created` | client | `ClientService.create()` | ✅ |
| `EVENT_CLIENT_UPDATED` | `client.updated` | client | `ClientService.update()` | ✅ |
| `EVENT_CLIENT_DELETED` | `client.deleted` | client | `ClientService.delete()` | ✅ |
| `EVENT_PROPERTY_CREATED` | `property.created` | property | `PropertyService.create()` | ✅ |
| `EVENT_PROPERTY_UPDATED` | `property.updated` | property | `PropertyService.update()` | ✅ |
| `EVENT_PROPERTY_DELETED` | `property.deleted` | property | `PropertyService.delete()` | ✅ |
| `EVENT_DEAL_CREATED` | `deal.created` | deal | `DealService.create()` | ✅ |
| `EVENT_DEAL_UPDATED` | `deal.updated` | deal | `DealService.update()` | ✅ |
| `EVENT_DEAL_DELETED` | `deal.deleted` | deal | `DealService.delete()` | ✅ |
| `EVENT_DOCUMENT_CREATED` | `document.created` | document | `DocumentPackageService.attach_document()` | ✅ |
| `EVENT_DOCUMENT_DELETED` | `document.deleted` | document | `DocumentPackageService.detach_document()` | ✅ |
| `EVENT_DOCUMENT_READY` | `document.ready` | document | `mark_document_ready()` (см. §3) | ✅ |
| `EVENT_LEAD_CONVERTED` | `lead.converted` | lead | `LeadService.convert_lead()` | ✅ |
| `EVENT_LEAD_MERGED` | `lead.merged` | lead | `LeadService.merge_leads()` | ✅ |

**Дополнительные события (без констант):**
| event_type | entity_type | Где эмитится | Реально эмитится? |
|-----------|-------------|--------------|:---:|
| `compliance.recheck_requested` | regulation | `RegulationImpactServiceV2.evaluate_regulation_change()` | ✅ |
| `regulation.updated` | regulation | `RegulationSyncServiceV2.sync_source()` | ✅ |

**Всего определено:** 14 констант + 2 неконстантных
**Всего реально эмитится:** 16 событий
**Типы entity:** client, property, deal, document, lead, regulation

### 1.3 Какие события НЕ эмитятся (определены, но код не вызывается)

- `POST /upload` в `api/routes/documents.py` не эмитит `document.created` — сохраняет документ в БД, но не создаёт событие
- Delete endpoint для документов отсутствует — `EVENT_DOCUMENT_DELETED` эмитится только из `DocumentPackageService.detach_document()` (открепление от папки, не удаление документа)

---

## 2. Current State — DomainEventBus

### 2.1 Архитектура

**Файл:** `backend/core/domain_events.py`

```
DomainEventBus (класс)
  └── _handlers: dict[str, list[EventHandler]]  — в памяти
  ├── register(event_type, handler)              — синхронно
  ├── register_all(handlers_dict)                — синхронно
  └── async emit(event)                          — async, последовательно вызывает handler'ы
      └── Каждый handler wrapped в try/except — ошибки логируются, не прерывают цепочку

get_event_bus() → глобальный singleton
  └── _bus: DomainEventBus | None = None
```

**Ключевые характеристики:**
- **Sync singleton** — один экземпляр на весь процесс
- **Async emit** — handler'ы вызываются `await` последовательно
- **In-memory handlers** — регистрация не сохраняется при перезапуске
- **Нет персистентности** — события живут только в памяти, теряются при падении процесса

### 2.2 Где и как регистрируются handler'ы

| Файл | Контекст | Когда вызывается |
|------|----------|-----------------|
| `backend/main.py` (lifespan startup) | `register_sync_handlers(get_event_bus())` | При старте FastAPI |
| `backend/api/routes/agent.py` (module level) | `_register_event_handlers()` → `register_sync_handlers(get_event_bus())` | При первом импорте модуля |

**Двойная регистрация:** handler'ы регистрируются дважды — один раз в `main.py:lifespan()`, другой раз в `agent.py` при импорте. Поскольку `register()` просто добавляет handler в список, это приводит к дублированию handler'ов: при эмиссии каждый handler вызывается дважды.

### 2.3 Зарегистрированные handler'ы

**Файл:** `backend/core/event_handlers.py`

Функция `register_sync_handlers()` создаёт словарь:

| event_type | Handler'ы |
|-----------|-----------|
| `client.created` | `graph_sync_handler`, `audit_handler` |
| `client.updated` | `graph_sync_handler`, `audit_handler` |
| `client.deleted` | `graph_sync_handler`, `audit_handler` |
| `property.created` | `graph_sync_handler`, `audit_handler` |
| `property.updated` | `graph_sync_handler`, `audit_handler` |
| `property.deleted` | `graph_sync_handler`, `audit_handler` |
| `deal.created` | `graph_sync_handler`, `audit_handler` |
| `deal.updated` | `graph_sync_handler`, `audit_handler` |
| `deal.deleted` | `graph_sync_handler`, `audit_handler` |
| `document.created` | `graph_sync_handler`, `embedding_sync_handler`, `search_index_handler`, `audit_handler` |
| `document.deleted` | `graph_sync_handler`, `embedding_sync_handler`, `search_index_handler`, `audit_handler` |
| `lead.converted` | `graph_sync_handler`, `audit_handler` |
| `lead.merged` | `graph_sync_handler`, `audit_handler` |

**Handler implementation:**

| Handler | Что делает |
|---------|-----------|
| `graph_sync_handler` | Синхронизирует CRM-сущность с Knowledge Graph через `GraphLifecycleService.sync_entity()` |
| `embedding_sync_handler` | **Stub** — только логирует вызов, реальной перестройки embedding нет |
| `search_index_handler` | **Stub** — только логирует вызов, реального обновления индекса нет |
| `audit_handler` | **Stub** — только логирует событие через structlog |

### 2.4 Обработка ошибок

```python
async def emit(self, event: DomainEvent) -> None:
    for handler in handlers:
        try:
            await handler(event)
        except Exception as e:
            logger.error("event_handler_failed", ...)
```

- **Retry: НЕТ** — упавший handler не перезапускается
- **Dead letter: НЕТ** — ошибка только логируется
- **Circuit breaker: НЕТ** — постоянно падающий handler не отключается
- **Ordering:** handler'ы вызываются последовательно. Если первый упал, остальные продолжают

### 2.5 Проблема: `loop.create_task()` из sync контекста

**Файл:** `backend/services/document_lifecycle.py:166`

```python
# mark_document_ready() — sync функция
bus = event_bus or get_event_bus()
try:
    loop = asyncio.get_running_loop()
    loop.create_task(bus.emit(event))
except RuntimeError:
    # No running event loop — log and continue
    logger.warning("no_event_loop", event_type=EVENT_DOCUMENT_READY)
```

**Проблемы:**
1. **Fire-and-forget из sync контекста** — событие эмитится асинхронно, но `mark_document_ready()` уже вернулся
2. **Нет await** — нельзя узнать, было ли событие обработано
3. **Теряется контекст** — если процесс упадёт между созданием task и его выполнением, событие потеряно
4. **Нет гарантии** — `create_task()` может быть отложен event loop'ом на неопределённое время
5. **Двойная регистрация handler'ов** (см. §2.2) — каждый handler вызывается дважды, но ошибку можно заметить только в логах

**ВАЖНО:** Это **осознанное техническое ограничение**, зафиксированное в Stream 0 proposal. План устранения: Stream 3 введёт Event Backbone с durable delivery.

---

## 3. Current State — Transaction Boundaries

### 3.1 Flow для `mark_document_ready()`

```
POST /{document_id}/mark-ready (FastAPI route)
  │
  ├── 1. repo.get(document_id)              ← SELECT из PostgreSQL
  │
  ├── 2. mark_document_ready(doc)           ← sync функция
  │     ├── transition_document(doc)        ← мутирует doc.status
  │     ├── создаёт DomainEvent
  │     └── loop.create_task(bus.emit())    ← fire-and-forget! (см. §2.5)
  │
  ├── 3. repo.save(doc)                     ← INSERT ... ON CONFLICT DO UPDATE
  │     ├── conn = psycopg2.connect()
  │     ├── cur.execute(INSERT ...)
  │     └── conn.commit()
  │
  └── 4. return response                    ← HTTP 200
```

### 3.2 Разрыв между save и event emit

**Точка истины:** `repo.save(doc)` → `conn.commit()` (строка 237 в `document_lifecycle.py`)

**Event emission** происходит ДО commit, но асинхронно (через `create_task`). Фактический порядок:

```
1. transition_document(doc)    — мутация в памяти
2. loop.create_task(bus.emit)  — fire-and-forget (событие в очереди event loop)
3. repo.save(doc)              — INSERT ... ON CONFLICT (свой commit)
4. conn.commit()               — транзакция зафиксирована
--- async gap ---
5. bus.emit() выполняется      — handler'ы вызываются
```

**Проблема:** Если процесс упадёт между шагами 2 и 5:
- **save уже выполнен** → статус документа в БД = READY
- **event НЕ эмичен** → handler'ы (graph sync, embedding, search, audit) не вызваны
- **Нет механизма восстановления** — событие потеряно навсегда

### 3.3 Для async сервисов (ClientService, PropertyService, DealService)

```
async def create():
    obj = await super().create(**kwargs)    ← flush (внутри одной транзакции)
    await self._emit(EVENT_CLIENT_CREATED)  ← emit в той же async функции
    # session.commit() — где-то выше, не здесь
```

- Здесь emit **внутри** транзакции (до commit). Если commit не удался → событие уже было отправлено handler'ам, хотя транзакция откатилась
- Нет outbox — событие обрабатывается handler'ами до подтверждения БД-транзакции

### 3.4 Вывод: нет единой точки истины

- **Нет outbox** — нет гарантии, что событие записано транзакционно с данными
- **Нет двухфазного commit** — save и event emission не атомарны
- **Event теряется** при падении процесса после save, но до emit
- **Event эмитится до commit** в async сервисах — если commit упадёт, handler'ы уже отработали с некорректными данными

---

## 4. Current State — Consumers

### 4.1 Список handler'ов / подписчиков

| Handler | Тип | Статус | Зависит от события |
|---------|-----|--------|-------------------|
| `graph_sync_handler` | Graph sync в Knowledge Graph | Реальный (создаёт/обновляет GraphNode) | client.*, property.*, deal.*, document.*, lead.* |
| `embedding_sync_handler` | Embedding rebuild | **Stub** (только log) | document.* |
| `search_index_handler` | Search index update | **Stub** (только log) | document.* |
| `audit_handler` | Audit log | **Stub** (только log через structlog) | Все события |

### 4.2 Кто зависит от событий сейчас

1. **GraphSync** — единственный реальный consumer. События `client.created`, `property.created`, `deal.created` и т.д. триггерят синхронизацию с Knowledge Graph
2. **Audit log** — формально зарегистрирован, но пишет только в structlog (не в отдельную audit-таблицу)
3. **Embedding / Search** — заглушки, не реализованы

### 4.3 Consumer-модель

- **Нет consumer contract** — handler принимает `DomainEvent` напрямую, без envelope
- **Нет idempotency** — если событие продублируется (при retry на уровне event loop), handler выполнится повторно
- **Нет dedup** — event_id не проверяется, processed_events table не существует
- **Нет ordering guarantees** — handler'ы вызываются последовательно, но порядок доставки не гарантирован на уровне инфраструктуры
- **Нет consumer health check** — упавший consumer не детектируется

---

## 5. ADR-030 Compliance

### 5.1 Ключевые решения ADR-030

ADR-030 (2026-07-24, статус Draft) выбирает модель **Append-only Event Log + отдельное текущее состояние** (НЕ full Event Sourcing).

| Решение | Суть |
|---------|------|
| Append-only | Никаких UPDATE/DELETE событий. Отмена — компенсирующими событиями |
| Текущее состояние отдельно | State хранится в проекциях, не выводится из событий |
| События для аудита | Полная и неизменная история |
| События для интеграции | Event Backbone между Streams |
| События для replay | Восстановление projection'ов |
| События НЕ единственный источник истины | Business State ≠ Event Stream |

### 5.2 Что из ADR уже реализовано

**Ничего.** ADR-030 — это архитектурное решение **для Stream 3**, а Stream 3 не реализован. Текущая реализация:

- DomainEventBus — **in-memory**, не append-only
- **Нет** event log в БД
- **Нет** outbox
- **Нет** replay
- **Нет** delivery guarantees
- Events — единственный канал уведомления, но не хранятся

### 5.3 Что предстоит реализовать в Stream 3

| Требование ADR-030 | Статус |
|--------------------|--------|
| Append-only event log | ❌ Нет |
| Transactional Outbox | ❌ Нет |
| At-least-once delivery | ❌ Нет (at-most-once, best-effort) |
| FIFO per aggregate | ❌ Нет |
| Replay model | ❌ Нет |
| Event Envelope (BusinessEvent) | ❌ Нет (используется DomainEvent) |
| Cross-stream contracts | ❌ Нет |
| IEventRepository / IOutboxRepository | ❌ Нет |
| Compensating events registry | ❌ Нет |

---

## 6. Problems Summary

### P1. События только в памяти
DomainEventBus хранит всё в `dict[str, list[EventHandler]]`. При перезапуске процесса:
- Все незаэмиченные событие теряются
- Регистрация handler'ов начинается заново
- Нет истории событий

### P2. Нет гарантии доставки
- `loop.create_task()` из sync контекста — fire-and-forget
- Нет confirmation от handler'ов
- Нет retry при падении handler'а
- Event теряется при падении процесса между save и emit

### P3. Нет replay
- События не сохраняются в durable storage
- Нельзя восстановить состояние consumer'а из событий
- Граф-синк не может быть перестроен из истории событий

### P4. Нет истории событий
- После обработки handler'ами событие «исчезает»
- Нет append-only журнала
- Нет audit trail в БД (только structlog в stdout)

### P5. Нет idempotency tracking
- Одно и то же событие может быть обработано дважды (при двойной регистрации handler'ов — проблема из §2.2)
- Нет `processed_events` таблицы
- Нет `event_id` dedup у consumer'ов

### P6. Нет consumer contract
- Handler'ы принимают `DomainEvent` напрямую — изменение формата сломает всех consumer'ов
- Нет EventEnvelope с version/source/metadata
- Нет backward compatibility механизма

### P7. Async emit из sync — хрупкий паттерн
```python
loop.create_task(bus.emit(event))
```
- Падает, если нет running loop (есть fallback, но событие теряется)
- Нельзя узнать, когда emit завершился
- Нельзя дождаться результата
- Task может быть отложен event loop'ом

### P8. Двойная регистрация handler'ов
- `main.py` и `agent.py` оба вызывают `register_sync_handlers()`
- Каждый handler регистрируется дважды → при эмиссии вызывается дважды
- Graph sync, audit и заглушки выполняются ×2 без необходимости

### P9. Нет транзакционной целостности save + emit
- В sync flow (`mark_document_ready`): save в psycopg2, emit через create_task — не атомарны
- В async flow (ClientService и др.): emit до commit — событие летит handler'ам до фиксации транзакции
- При падении на любом этапе — данные рассинхронизируются

### P10. Entity_ID нестабилен
- `mark_document_ready()` использует `uuid.uuid4()` для entity_id — новый UUID каждый раз, а не `doc.document_id`
- event_id (entity_id) не является идентификатором документа — невозможно установить связь между событием и документом без payload

---

## 7. Target Direction (не реализация!)

Целевая архитектура Event Backbone для Stream 3:

```
Domain Model
    │
    ▼
BusinessEvent (frozen dataclass, append-only)
    │
    ▼
Transactional Outbox (INSERT event + outbox in same DB transaction)
    │
    ▼
Append-only Event Store (durable log — compliance.business_events)
    │
    ▼
Event Backbone Publisher (at-least-once delivery)
    │
    ├──► Consumer 1 (idempotent, with dedup)
    ├──► Consumer 2 (idempotent, with dedup)
    └──► Consumer N (idempotent, with dedup)
    │
    ▼
Replay Model (full/partial recovery from Append-only Log)
```

**Важное ограничение:**
- **Не делаем Event Sourcing** (ADR-030)
- Append-only Event Backbone — события как **интеграционный поток**, не как единственный источник состояния
- Текущее состояние бизнес-агрегатов хранится отдельно (в проекциях)

**Ключевые компоненты, описанные в Proposal Stream 3 и Frozen в Architecture Freeze:**
1. **BusinessEvent** — новая доменная модель (frozen, append-only, с event_id/metadata/correlation/causation/aggregate/sequence/payload)
2. **Transactional Outbox** — атомарная запись события + outbox в одной транзакции
3. **Append-only Event Store** — `compliance.business_events` таблица (только INSERT)
4. **Publisher** — polling из outbox, at-least-once delivery в брокер
5. **Idempotent Consumers** — dedup по event_id
6. **Replay** — восстановление consumer'ов из event store

---

## 8. Что уже готово для Stream 3

### 8.1 DocumentReady контракт (Stream 0)
- Event payload определён: `document_id`, `organization_id`, `status`, `previous_status`, `profile`
- DomainEventBus встроен в `mark_document_ready()`
- API endpoint (`POST /{document_id}/mark-ready`)
- Зафиксировано ограничение: **best-effort, at-most-once** — это сознательное решение Stream 0

### 8.2 ADR-030
- Решение принято: Append-only Event Log + отдельное текущее состояние
- Full Event Sourcing отклонён
- Инварианты зафиксированы:
  - События — append-only (никаких UPDATE/DELETE)
  - Текущее состояние — отдельные проекции
  - События НЕ единственный источник истины

### 8.3 Architecture Freeze (Stream 3)
**Frozen decisions (7 шт.):**
| # | Decision | Reference |
|:-:|:---------|:----------|
| D1 | Append-only Log | ADR-030 |
| D2 | Transactional Outbox | Proposal §4 |
| D3 | At-least-once Delivery | Proposal §8 |
| D4 | FIFO per Aggregate | Proposal §6 |
| D5 | Replay Model | Proposal §7 |
| D6 | Event Envelope | Proposal §2.4–2.5 |
| D7 | Cross-stream Contracts | Proposal §9.10 |

**Repository interfaces frozen:**
- `IEventRepository` (append, append_batch, next_sequence, get_event, replay_by_aggregate, replay_by_type, count_events, get_events_by_correlation)
- `IOutboxRepository` (enqueue, fetch_pending, mark_published, mark_failed, fetch_failed, retry)

---

## 9. Чего не хватает

### 9.1 Отсутствуют полностью

| Компонент | Описание | Где должно быть |
|-----------|----------|-----------------|
| **Outbox table/schema** | Таблица `compliance.outbox` с полями event_id, status, retry_count, last_error | Proposal §4.2 (SQL DDL существует в proposal) |
| **Append-only event store** | Таблица `compliance.business_events` (только INSERT) | Proposal §4 (описано, не реализовано) |
| **Event Envelope (BusinessEvent)** | Новая доменная модель вместо DomainEvent | Proposal §2.5 |
| **IEventRepository implementation** | SQLAlchemy реализация append-only repo | Proposal §4.4 |
| **IOutboxRepository implementation** | SQLAlchemy реализация outbox repo | Proposal §4.5 |
| **Publisher model** | Polling из outbox + публикация в брокер | Proposal §4.6 |
| **Retry policy** | Exponential backoff, max retries, dead letter | ❌ Даже в proposal — gap (Architecture Review §6) |
| **Consumer contract** | Формат EventEnvelope для downstream Streams | Proposal §9 |
| **Idempotency strategy** | Dedup по event_id, processed_events table | Proposal §7 (упоминается) |
| **Replay boundaries** | Оркестратор replay: full/partial, checkpointing | Proposal §7 (с gap'ами по Architecture Review) |
| **Bounded context для EventType** | EventType enum для Compliance событий | Proposal §2.2 |
| **EventSchemaRegistry** | Парсеры для разных версий payload | Proposal §5 |
| **Sequence generation** | Монотонный sequence_number внутри aggregate_id | Proposal §6 |
| **Compensating events registry** | Пары original/compensating EventType | Proposal §2.7 |

### 9.2 Gap'ы, отмеченные Architecture Review

| # | Пункт | Статус | Ключевой gap |
|:-:|:------|:-------|:-------------|
| 1 | ADR-019 | ❌ Missing | ADR про append-only vs event sourcing не создан (заменён ADR-030) |
| 2 | Replay | ⚠️ Partial | Очистка state, crash recovery, batch |
| 3 | Event Payload | ⚠️ Partial | Нет принципов, `producer` в payload, дублирование |
| 4 | Event Versioning | ⚠️ Partial | Нет `event_type_version`, нет аргументации |
| 5 | Ordering | ✅ Covered | Конкурентная запись — retry не описан |
| 6 | Outbox | ⚠️ Partial | Backoff, poison message, multi-instance docs |
| 7 | Cross-stream Contracts | ⚠️ Partial | Нет явного запрета на прямой SQL |

### 9.3 Инфраструктурные решения не приняты

- Конкретный брокер: RabbitMQ / Kafka / Redis Streams — **не выбран**
- Metrics/monitoring — **deferred** (Post-MVP)
- Connection pool для event store — **не определён**
- Deployment model publisher'а — **не определён** (sidecar? in-process?)

---

## 10. Итоговая таблица State

| Домен | Текущее состояние | Целевое (Stream 3) | Разрыв |
|:------|:------------------|:--------------------|:-------|
| Event Model | `DomainEvent` (mutable dataclass) | `BusinessEvent` (frozen, envelope) | Полный |
| Storage | In-memory | Append-only SQL table | Полный |
| Delivery | At-most-once, best-effort | At-least-once | Полный |
| Outbox | Нет | Transactional Outbox | Полный |
| Consumers | Sync handlers in-process | Idempotent consumers via broker | Полный |
| Replay | Нет | Full/partial replay | Полный |
| Ordering | Нет гарантий | FIFO per aggregate | Полный |
| Durability | Нет (все в памяти) | Durable event store | Полный |
| Observability | Structlog only | Metrics, DLQ monitoring | Полный |

**Резюме:** Текущий Event Backbone — это **временный, in-memory механизм** для синхронизации CRM с Knowledge Graph. Он не удовлетворяет ни одному из требований Stream 3. Переход к целевой архитектуре требует полной замены event model, storage, delivery механизма и consumer модели. Единственное готовое — это архитектурные решения (ADR-030, Architecture Freeze), контракт DocumentReady из Stream 0 и детальный proposal.

---

*Документ создан 2026-07-26. Phase 0 Discovery — Event Backbone.*
*Источники: domain_events.py, event_handlers.py, document_lifecycle.py, main.py, agent.py, ADR-030, Architecture Freeze, Architecture Review, Proposal Stream 3, Stream 0 proposal.*
