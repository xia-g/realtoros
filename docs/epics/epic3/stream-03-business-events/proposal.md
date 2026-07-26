---
title: "Phase 1 — Design Proposal: Stream 3 Event Backbone"
status: Draft
date: 2026-07-26
author: RealtorOS Architecture
---

# Phase 1 — Design Proposal: Stream 3 (Event Backbone)

> **Scope:** Event Backbone — outbox, delivery guarantees, consumer contract.
> Вводится durable, append-only событийная инфраструктура взамен существующего
> in-memory DomainEventBus.
>
> **Discovery:** `current-event-backbone.md` (Phase 0, 500 строк).
>
> **Sources:** `backend/core/domain_events.py`, `backend/core/event_handlers.py`,
> `backend/services/document_lifecycle.py`, `backend/main.py`,
> `backend/api/routes/agent.py`, `ADR-030`, `Architecture Freeze`,
> `Architecture Review Stream 3`.

---

## 1. Scope

### Добавляем

| Компонент | Описание |
|-----------|----------|
| **Event Envelope** | Единый формат события: `event_id`, `event_type`, `aggregate_id`, `occurred_at`, `version`, `payload`, `metadata` |
| **Append-only Event Storage** | Immutable, sequential write, readable history — таблица `business_events` (только INSERT, никаких UPDATE/DELETE) |
| **Outbox Pattern** | Устранить разрыв save/emit. Новый поток: `BEGIN → update document → insert outbox → COMMIT → publisher → consumer` |
| **Publisher** | Отдельный компонент, polling из outbox. At-least-once delivery. Retry + dead letter |
| **Consumer Contract** | `consume(event: IntegrationEvent) → Result`. Idempotency, retry, failure handling |
| **Replay (minimal)** | `event_id`, `from_timestamp`, `from_sequence`. Deterministic recovery для consumers |
| **Исправление P8** | Единый registry handler'ов. Убрать двойную регистрацию из `agent.py`. Регистрация только в `main.py lifespan` |

### Не входит в Stream 3 (❌)

| Что | Почему |
|-----|--------|
| Event Sourcing | ADR-030: append-only + отдельное состояние. Не full ES |
| Изменение Aggregate Model | `Document`, `Client`, `Deal` и др. остаются как есть. Состояние — в текущих таблицах |
| CQRS projections | Дефернуто — появится, когда Stream 4+ понадобится state projection |
| Kafka / RabbitMQ | Конкретный брокер не выбираем. Publisher абстрагирован через `IEventBroker` |
| Сложный workflow engine | Не требуется. Outbox → Publisher → Consumer — достаточно |
| Замена всех consumers | GraphSync остаётся. Embedding/Search/Audit — stub'ы. Мигрируем только механизм получения событий |
| Переписывание всех domain events | `DomainEvent` остаётся как внутренний механизм. Новый `IntegrationEvent` — для durable доставки |
| Изменение `DomainEvent` | Класс `DomainEvent` остаётся без изменений. Stream 0 и сервисы продолжают эмитить через него |

### Ключевое разграничение

```
DomainEvent (внутренний, in-memory)
    ↓
IntegrationEvent (frozen, durable, проходит через Outbox)
    ↓
Consumer Contract (at-least-once, idempotent)
```

`DomainEvent` — то, что эмитят сервисы сейчас. `IntegrationEvent` — новый durable контракт.
Stream 3 НЕ меняет, как сервисы создают `DomainEvent`. Он добавляет слой durable доставки ПОД ними.

---

## 2. Decision Log

### Decision 1: Append-only, Not Event Sourcing

**Решение:** Состояние остаётся в текущих таблицах. События — для интеграции, аудита,
синхронизации. НЕ для восстановления aggregate.

**Обоснование:**
- ADR-030 (2026-07-24) фиксирует Append-only Event Log + отдельное текущее состояние
- Full Event Sourcing отведён: overengineering для текущей доменной модели
- Агрегаты (Document, Client, Deal) — простые CRUD, не CQRS/ES-модели
- События нужны для: GraphSync, аудит, будущие embedding/search/notifications
- Восстановление состояния агрегата из событий никогда не потребуется — текущее состояние всегда в БД

**Статус:** Frozen (ADR-030).

### Decision 2: Outbox — источник гарантии доставки

**Решение:** Не DomainEventBus, а: Database transaction + Outbox record.
Транзакционная целостность save + event.

**Обоснование:**
- Сейчас: `save()` и `emit()` не атомарны. Event теряется при падении между save и emit.
- В async сервисах: emit до commit — событие уходит handler'ам до фиксации транзакции.
- Outbox решает: `BEGIN → save(entity) → insert outbox → COMMIT`.
- Если COMMIT успешен → событие гарантированно сохранено в outbox.
- Publisher polling'ит outbox и доставляет consumer'ам.

**Статус:** Accepted.

### Decision 3: Domain Event ≠ Integration Event

**Решение:** Разделяем `DomainEvent` (внутренний, in-memory) и `IntegrationEvent`
(durable, проходит через Outbox).

**Обоснование:**
- Сейчас `DomainEvent` — единственный формат. Все handlers принимают его напрямую.
- `DomainEvent` mutable, не имеет `event_id`, не frozen — не подходит для durable хранения.
- `IntegrationEvent` — новый frozen dataclass с Event Envelope, event_id, metadata.
- `DomainEvent` продолжает существовать как внутренний механизм сервисов (Stream 0).
- Stream 3 добавляет конвертацию `DomainEvent → IntegrationEvent` на уровне прокси/adapter.

**Пример:**
```python
# Остаётся как есть (Stream 0)
event = DomainEvent(event_type="document.ready", entity_type="document", ...)

# Добавляется (Stream 3)
integration_event = IntegrationEvent(
    event_id=uuid4(),
    event_type="document.ready",
    aggregate_type="Document",
    aggregate_id=doc.document_id,
    payload=event.payload,
    metadata=EventMetadata(...)
)
```

**Статус:** Accepted.

---

## 3. Event Lifecycle Contract

### Полный цикл

```
Domain action
    │
    ▼
DomainEvent (in-memory, через DomainEventBus)  ─── Продолжает работать как сейчас
    │
    ▼
Event Adapter (конвертирует DomainEvent → IntegrationEvent)
    │
    ▼
Outbox record (INSERT в event_outbox, в той же транзакции что и save)
    │
    ▼
Publisher (polling из outbox)
    │
    ├── at-least-once delivery
    │
    ▼
Consumer (идемпотентная обработка)
    │
    ├── ✅ success → mark_published
    └── ❌ failure → retry → dead letter
```

### Этапы

| # | Этап | Где | Гарантия |
|---|------|-----|----------|
| 1 | Domain action | Application service / use-case | — |
| 2 | DomainEvent создан | В памяти | — |
| 3 | DomainEvent эмичен | `DomainEventBus.emit()` (async, in-memory) | best-effort (как сейчас) |
| 4 | **NEW: Event Adapter перехватывает** | Event proxy в `emit()` | синхронно |
| 5 | **NEW: Outbox запись** | В той же DB транзакции что и save | ✅ durable |
| 6 | **NEW: Publisher читает** | polling (раз в N секунд) | at-least-once |
| 7 | **NEW: Consumer получает** | IntegrationEvent | at-least-once |
| 8 | **NEW: Processing result** | success / retry / dead letter | идемпотентно |

### Где меняется код

**Минимальная точка внедрения Outbox:**
- В `mark_document_ready()`: после `save()` добавляем `outbox_repo.enqueue(event)`
- В async сервисах (ClientService, PropertyService etc.): в том же `await self._emit()`
  или в application service после commit

**Publisher:**
- Новый модуль: `backend/infrastructure/event_publisher.py`
- Запускается как background task в `lifespan` (или отдельный процесс)
- Polling interval: configurable (default 1s)

---

## 4. Event Envelope

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "document.ready",
  "aggregate_type": "Document",
  "aggregate_id": "doc-uuid-1234-5678",
  "occurred_at": "2026-07-26T12:00:00Z",
  "version": 1,
  "payload": {
    "document_id": "doc-uuid-1234-5678",
    "organization_id": "org-uuid-0001",
    "status": "READY",
    "previous_status": "ANALYZED",
    "contract_number": "CT-2026-001"
  },
  "metadata": {
    "schema_version": 1,
    "producer": "document-lifecycle",
    "correlation_id": "corr-uuid-abc-123",
    "causation_id": null
  }
}
```

### Спецификация полей

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `event_id` | UUID v7 | ✅ | Глобально уникальный ID события. Time-ordered |
| `event_type` | string | ✅ | `{domain}.{action}` — `document.ready`, `client.created` |
| `aggregate_type` | string | ✅ | Тип агрегата: `Document`, `Client`, `Property`, `Deal`, `Lead` |
| `aggregate_id` | string | ✅ | Универсальный ID агрегата (см. §8) |
| `occurred_at` | ISO-8601 | ✅ | Когда событие произошло (из часов) |
| `version` | int | ✅ | Версия формата Envelope. Сейчас = 1 |
| `payload` | object | ✅ | Доменные данные события |
| `metadata.schema_version` | int | ✅ | Версия схемы payload |
| `metadata.producer` | string | ✅ | Имя сервиса-производителя |
| `metadata.correlation_id` | UUID | ❌ | Для группировки связанных событий |
| `metadata.causation_id` | UUID\|null | ❌ | Ссылка на событие-причину |

### Обоснование: без entity_id

Поле `entity_id` **НЕ вводится** в IntegrationEvent. Термин "entity" слишком размытый.
Все бизнес-сущности — это агрегаты: Document, Client, Property, Deal, Lead.

Вместо этого используем два поля:
- `aggregate_id` (string) — стабильный ID бизнес-сущности (document_id, client_id, deal_id)
- `event_id` (UUID) — глобально уникальный ID события

`entity_id` остаётся только в DomainEvent (для backward compatibility),
но в IntegrationEvent его нет.

### Python dataclass

```python
@dataclass(frozen=True)
class IntegrationEvent:
    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: datetime
    version: int = 1
    payload: dict
    metadata: dict | None = None
```

### Сериализация

`IntegrationEvent` → JSON → JSONB (в обеих таблицах: `business_events` и `event_outbox`).
Deserialization: `IntegrationEvent.from_dict()`. Никакой ORM для domain модели.

---

## 5. Outbox Model

### Таблица `event_outbox`

```sql
CREATE TABLE event_outbox (
    id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    event_type      VARCHAR(100)    NOT NULL,
    aggregate_type  VARCHAR(50)     NOT NULL,
    aggregate_id    VARCHAR(255)    NOT NULL,
    payload         JSONB           NOT NULL,       -- полный IntegrationEvent
    metadata        JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ,                    -- когда отправлено (NULL = pending)
    attempts        INTEGER         NOT NULL DEFAULT 0,
    last_error      TEXT,                           -- последняя ошибка публикации
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'published', 'failed', 'dead')),

    CONSTRAINT pk_event_outbox PRIMARY KEY (id)
);

-- Для polling
CREATE INDEX idx_outbox_status_created
    ON event_outbox (status, created_at)
    WHERE status = 'pending';

-- Для recovery failed событий
CREATE INDEX idx_outbox_status_attempts
    ON event_outbox (status, attempts)
    WHERE status = 'failed';
```

### Таблица `business_events` (append-only log)

```sql
CREATE TABLE business_events (
    event_id        UUID            NOT NULL,
    event_type      VARCHAR(100)    NOT NULL,
    aggregate_type  VARCHAR(50)     NOT NULL,
    aggregate_id    VARCHAR(255)    NOT NULL,
    occurred_at     TIMESTAMPTZ     NOT NULL,
    version         INTEGER         NOT NULL DEFAULT 1,
    payload         JSONB           NOT NULL,
    metadata        JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT pk_business_events PRIMARY KEY (event_id)
);

-- Для replay по aggregate
CREATE INDEX idx_be_aggregate
    ON business_events (aggregate_type, aggregate_id, occurred_at);

-- Для replay по типу
CREATE INDEX idx_be_event_type
    ON business_events (event_type, occurred_at);

-- Для replay по времени
CREATE INDEX idx_be_occurred_at
    ON business_events (occurred_at);
```

### Почему две таблицы?

| Таблица | Назначение | Retention |
|---------|-----------|-----------|
| `event_outbox` | Очередь для Publisher, mutable (status меняется) | Очищается после публикации |
| `business_events` | Append-only архив, immutable | Permanent (для replay, аудита) |

Outbox запись пишется в той же транзакции, что и бизнес-данные.
`business_events` может писаться в той же транзакции или асинхронно — решение deferred.

---

## 6. Delivery Guarantees

### Таблица гарантий по слоям

| Layer | Guarantee | Механизм |
|-------|-----------|----------|
| **Domain Event** | in-memory (best-effort) | `DomainEventBus.emit()` — как сейчас. Не меняется |
| **Outbox** | ✅ durable (в DB транзакции) | `BEGIN → save + insert outbox → COMMIT`. Если COMMIT успешен — событие сохранено |
| **Publisher → Consumer** | ✅ at-least-once | После успешного ответа consumer'а → `mark_published()`. Если ответа нет → retry |
| **Consumer** | ✅ idempotent | Dedup по `event_id`. Consumer сам проверяет `processed_events` |
| **Replay** | ✅ deterministic | Одинаковые события → одинаковый результат. Порядок = `occurred_at` + `event_id` |

### Что это значит на практике

1. **Outbox гарантирует:** событие не потеряется после COMMIT транзакции
2. **At-least-once означает:** событие может прийти дважды — consumer должен быть идемпотентным
3. **Idempotency означает:** обработка того же `event_id` второй раз не меняет состояние
4. **Replay означает:** можно перестроить состояние consumer'а, применив события в том же порядке

### Что НЕ гарантируется

- **Exactly-once** — не поддерживается. Требует distributed transactions
- **Глобальный порядок** — события разных aggregate не упорядочены
- **FIFO между разными aggregate** — не гарантируется
- **Zero latency** — Publisher polling → задержка от 100ms до N секунд (configurable)

---

## 7. Consumer Contract

### Интерфейс

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConsumerResult:
    success: bool
    error: str | None = None
    retryable: bool = True  # False = poison message → dead letter


class EventConsumer(Protocol):
    """Контракт consumer'а событий."""

    async def consume(self, event: IntegrationEvent) -> ConsumerResult:
        """Обработать событие. Вернуть успех/ошибку."""
        ...
```

### Idempotency

**Каждый consumer обязан быть идемпотентным.**

Механизм:
1. Consumer хранит `processed_events` (таблица или in-memory set)
2. При получении события: `SELECT 1 FROM processed_events WHERE event_id = ?`
3. Если уже обработано → `ConsumerResult(success=True)` (skip)
4. Если новое → обработать, записать `event_id` в `processed_events`
5. При ошибке → не записывать `event_id` → retry подхватит

```python
async def consume(self, event: IntegrationEvent) -> ConsumerResult:
    # 1. Dedup
    if await self._is_processed(event.event_id):
        return ConsumerResult(success=True)  # уже обработано

    try:
        await self._process(event)
        await self._mark_processed(event.event_id)
        return ConsumerResult(success=True)
    except Exception as e:
        return ConsumerResult(success=False, error=str(e), retryable=True)
```

### event_id identity через retry

event_id должен быть:
- уникальным
- стабильным
- неизменным при retry

```
publish attempt #1:
  event_id = "abc-123"
  → FAIL

publish attempt #2 (retry):
  event_id = "abc-123"  ← тот же!
  → SUCCESS
```

Это важно для deduplication: если retry меняет event_id, consumer не сможет определить,
что это то же самое событие.

**Реализация:** event_id генерируется в момент создания IntegrationEvent (в EventAdapter)
и передаётся в outbox как есть. Publisher никогда не пересоздаёт event_id.
При retry publisher повторно отправляет тот же IntegrationEvent с тем же event_id.

### Consumer Processing State

Каждый consumer должен иметь механизм хранения факта обработки события.

Минимальная схема (таблица `processed_events`):

```sql
CREATE TABLE consumer_processed_events (
    consumer_name   VARCHAR(100)    NOT NULL,
    event_id        UUID            NOT NULL,
    processed_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT pk_consumer_processed PRIMARY KEY (consumer_name, event_id)
);
```

Правила:
- При получении события: `SELECT 1 FROM consumer_processed_events WHERE consumer_name = ? AND event_id = ?`
- Если есть → skip (уже обработано)
- Если нет → обработать → INSERT
- INSERT и бизнес-логика — в одной транзакции consumer'а
- При ошибке INSERT не делается → retry подхватит

Для in-memory consumer'ов (stub'ы) допустим in-memory set,
но для production consumer'ов (GraphSync) — обязательная таблица.

**Отличие от Idempotency (выше):** Там описана логика обработки на уровне кода.
Здесь — физическая схема хранения processed_events. Каждый consumer использует
свою таблицу (или свой schema namespace).

### Retry Policy

| Параметр | Значение |
|----------|----------|
| Max retries | 3 |
| Backoff | Exponential: 1s → 2s → 4s |
| После max retries | Status → `failed`. После 3 failed → `dead` |
| Dead letter | Ручной возврат (админка или API). Alert в лог |

### Dead Letter

- `status = 'dead'` — событие не будет picked up publisher'ом
- Alert: `logger.error("poison_event", event_id=..., event_type=..., last_error=...)`
- Recovery: admin API `POST /events/{id}/retry` → status = `pending`

### Текущие consumers — миграция

| Consumer | Статус | Механизм сейчас | Механизм после Stream 3 |
|----------|--------|-----------------|------------------------|
| **GraphSync** | ✅ Реальный | DomainEventBus (in-memory) | IntegrationEvent через publisher |
| **Embedding** | ⚠️ Stub (log only) | DomainEventBus (in-memory) | IntegrationEvent через publisher |
| **Search Index** | ⚠️ Stub (log only) | DomainEventBus (in-memory) | IntegrationEvent через publisher |
| **Audit** | ⚠️ Stub (log only) | DomainEventBus (in-memory) | IntegrationEvent → audit таблица |

**Миграция:**
1. Фаза 1: Publisher доставляет события. Consumers получают через publisher.
2. Фаза 2: Consumers переходят на `IntegrationEvent`.
3. Фаза 3: Старый `DomainEventBus.register()` — удаляется.

**График:** GraphSync мигрируется первым. Stub'ы — по мере реализации.

### Исправление P8: Единый EventRegistry

**Проблема:** `register_sync_handlers()` вызывается дважды:
- `main.py:lifespan` (правильное место)
- `agent.py:_register_event_handlers()` при импорте (неправильно)

**Решение:**

```python
# backend/core/event_registry.py — НОВЫЙ ФАЙЛ

import logging

from backend.core.event_handlers import register_sync_handlers
from backend.core.domain_events import get_event_bus

_registry_initialized = False

def ensure_event_registry() -> None:
    """Инициализировать event registry ровно один раз."""
    global _registry_initialized
    if _registry_initialized:
        return
    register_sync_handlers(get_event_bus())
    _registry_initialized = True
    logger.info("event_registry_initialized")
```

**Изменения:**
1. `main.py:lifespan`: `ensure_event_registry()` вместо `register_sync_handlers(get_event_bus())`
2. `agent.py`: Удалить `_register_event_handlers()` и вызов `_register_event_handlers()` на module level
3. `backend/core/event_registry.py`: Новый файл с `ensure_event_registry()`

**Где меняется:**

```patch
# main.py
- register_sync_handlers(get_event_bus())
+ ensure_event_registry()

# agent.py — УДАЛИТЬ:
- def _register_event_handlers():
-     register_sync_handlers(get_event_bus())
- _register_event_handlers()
```

---

## 8. aggregate_id + event_id (P10)

### Проблема

Сейчас `mark_document_ready()` создаёт:
```python
entity_id=uuid.uuid4()  # ← новый UUID каждый раз!
```

Этот UUID не связан с `doc.document_id`. Нельзя установить, к какому документу
относится событие, без анализа `payload`.

### Решение

Вводим два уровня идентификации, **без общего поля entity_id**:

```json
{
  "aggregate_type": "Document",
  "aggregate_id": "doc-uuid-1234",
  "event_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Поле | Значение | Стабильность |
|------|----------|-------------|
| `aggregate_id` | ID доменной сущности (document_id, client_id, deal_id) | Стабильный. Один на всю жизнь сущности |
| `aggregate_type` | Тип сущности | Фиксированный |
| `event_id` | UUID события | Уникальный на каждое событие |

Поле `entity_id` **отсутствует** в IntegrationEvent. Термин "entity" слишком размытый.
Все бизнес-сущности — это агрегаты: Document, Client, Property, Deal, Lead.

`entity_id` остаётся только в DomainEvent (backward compatibility с текущим кодом сервисов),
но в IntegrationEvent используются только `aggregate_id` + `event_id`.

### Для Document:

```python
aggregate_id = doc.document_id  # стабильный ID документа
aggregate_type = "Document"
event_id = uuid.uuid4()  # уникальный ID события
```

### Для Client:

```python
aggregate_id = client.client_id  # стабильный ID клиента
aggregate_type = "Client"
```

### aggregate_id — универсальный идентификатор

- Для Document: `aggregate_id = document_id`
- Для Client: `aggregate_id = client_id`
- Для Property: `aggregate_id = property_id`
- Для Deal: `aggregate_id = deal_id`
- Для Lead: `aggregate_id = lead_id`

`aggregate_type` дискриминирует тип. Комбинация `(aggregate_type, aggregate_id)`
уникальна и стабильна.

---

## 9. Test Strategy

### 9.1 Outbox Tests

| # | Сценарий | Input | Expected |
|---|----------|-------|----------|
| 1 | Event создаётся в outbox | `IntegrationEvent`, entity saved | `SELECT * FROM event_outbox WHERE event_id = ?` → 1 row, `status = 'pending'` |
| 2 | Event сохраняется после commit | outbox enqueue → commit | Row exists after commit |
| 3 | Transaction rollback удаляет event | outbox enqueue → rollback | Row NOT exists after rollback |
| 4 | Duplicate event_id не вставляется | Дважды enqueue тот же event | Вторая попытка → error (unique constraint) |

### 9.2 Publisher Tests

| # | Сценарий | Input | Expected |
|---|----------|-------|----------|
| 1 | Unpublished events выбираются | 3 pending events | `fetch_pending(limit=5)` → 3 events |
| 2 | Publish меняет статус | `mark_published(event)` | `status = 'published'`, `published_at` not null |
| 3 | Mark failed works | `mark_failed(event, error)` | `status = 'failed'`, `attempts++`, `last_error` set |
| 4 | Retry работает | `fetch_failed(max_retries=3)` | Returns events with `attempts < 3` |
| 5 | Dead letter after max retries | 3 failed attempts | `status = 'dead'`, not returned by `fetch_failed()` |
| 6 | FOR UPDATE SKIP LOCKED concurrency | 2 publishers одновременно | Каждый берёт свою порцию, без deadlock |

### 9.3 Consumer Tests

| # | Сценарий | Input | Expected |
|---|----------|-------|----------|
| 1 | Event обрабатывается один раз | new event → consume | `processed_events` has `event_id`. State updated once |
| 2 | Duplicate event не ломает state | тот же event второй раз | `ConsumerResult(success=True)`. State unchanged |
| 3 | Exception → retry | consumer raises | `ConsumerResult(success=False, retryable=True)`. `attempts++` in outbox |
| 4 | Non-retryable → dead letter | consumer raises, `retryable=False` | `ConsumerResult(success=False, retryable=False)`. Status → `failed` |
| 5 | Consumer health check | ping consumer | Consumer не завис, не упал |

### 9.4 Replay Tests

| # | Сценарий | Input | Expected |
|---|----------|-------|----------|
| 1 | Deterministic replay | Те же события, 2 раза | Одинаковое состояние после каждого replay |
| 2 | Replay with checkpoint | 100 events → replay from seq 50 | Состояние = состояние после 50 events |
| 3 | Replay empty store | No events | Consumer state unchanged |
| 4 | Replay with missing events | Replay from seq 10, events 1-9 deleted | Gap detected, logged |

### 9.5 Integration Tests (P8 fix)

| # | Сценарий | Input | Expected |
|---|----------|-------|----------|
| 1 | Single registration | `ensure_event_registry()` → `emit()` | Каждый handler вызван ровно 1 раз |
| 2 | Double call | `ensure_event_registry()` × 2 | handlers not duplicated (idempotent guard) |
| 3 | GraphSync не дублируется | event → consumer | GraphNode synced once |

### 9.6 Additional Tests

| # | Сценарий | Input | Expected |
|---|----------|-------|----------|
| 1 | Outbox atomicity: save fails → no event | save(entity) → rollback | `SELECT * FROM event_outbox WHERE event_id = ?` → 0 rows |
| 2 | Retry stability: same event_id on retry | publish fails with event_id="abc-123" → retry | Повторная отправка с тем же event_id="abc-123". Consumer видит один event_id |
| 3 | Consumer duplicate: same event delivered twice | deliver(event) × 2 | Consumer обрабатывает ровно 1 раз. `consumer_processed_events` — 1 row |
| 4 | Replay determinism: events A+B+C → same state | replay(A,B,C) × 2 | После первого и второго replay состояние consumer'а идентично |

---

## 10. Architecture Review Questions — Ответы

### Q1: Где физически хранится Event?

**Ответ:** В двух таблицах:
1. `event_outbox` — mutable, для Publisher (status: pending → published/failed/dead)
2. `business_events` — immutable, append-only архив для replay и аудита

Обе в PostgreSQL, `compliance` schema (или `events` schema — TBD).

### Q2: Когда создаётся Outbox запись?

**Ответ:** В том же месте, где сейчас `save()` + `emit()`.
В application service или repository, внутри одной транзакции.

Для `mark_document_ready()`:
```python
# NEW FLOW
conn = repo._connect()
try:
    repo.save(doc, conn=conn)  # pass connection
    outbox_repo.enqueue(event, conn=conn)  # same transaction
    conn.commit()
finally:
    conn.close()
```

Для async сервисов (ClientService, etc.):
```python
async def create(self, **kwargs):
    obj = await super().create(**kwargs)  # внутри транзакции
    event = build_integration_event(obj)
    await self._outbox_repo.enqueue(event)  # та же сессия
    await self._session.commit()
```

### Q3: Как гарантируется атомарность save + event?

**Ответ:** Через единую DB транзакцию:
```
BEGIN
  → update/save domain entity
  → INSERT INTO event_outbox (...)
COMMIT
```

Если COMMIT успешен → и данные, и event сохранены.
Если COMMIT не удался → ничего не сохранено. Publisher ничего не увидит.

**Нагрузка на транзакцию:** INSERT в outbox — лёгкая операция (индексированный JSONB).
Не замедляет бизнес-транзакцию.

### Q4: Что является публичным контрактом для consumers?

**Ответ:** `IntegrationEvent` (Event Envelope из §4). Не `DomainEvent`.

Consumer никогда не видит `DomainEvent` напрямую. Всегда через Envelope.
Это защищает consumer'ов от изменений внутреннего формата `DomainEvent`.

### Q5: Как отличаем Domain Event от Integration Event?

| | DomainEvent | IntegrationEvent |
|--|------------|-----------------|
| **Назначение** | Внутреннее уведомление | durable доставка downstream |
| **Хранение** | In-memory (теряется при падении) | Durable (outbox + business_events) |
| **Формат** | Mutable dataclass | Frozen dataclass, Envelope |
| **event_id** | Нет (entity_id — не уникальный) | ✅ UUID v7 |
| **Aggregate** | `entity_type` + `entity_id` | `aggregate_type` + `aggregate_id` |
| **Metadata** | Нет | schema_version, producer, correlation |
| **Delivery** | best-effort, at-most-once | at-least-once, retry, dead letter |

### Q6: Retry backoff и poison message?

**Ответ:**
- Exponential backoff: 1s → 2s → 4s (configurable)
- После 3 retry → status = `failed`
- После 3 consecutive failed → status = `dead`
- Poison message policy: alert + manual intervention (retry API)
- См. §7 (Retry Policy + Dead Letter)

### Q7: Concurrent publisher'ы?

**Ответ:** `SELECT ... FROM event_outbox WHERE status = 'pending' FOR UPDATE SKIP LOCKED`
поддерживает multiple publisher instances. Каждый берёт свои строки.
Graceful shutdown: in-flight events на следующем poll'е снова pending.

### Q8: Запрет на прямой SQL к business_events?

**Ответ:** зафиксировано в Architecture Freeze (D7):
> Downstream Streams НЕ имеют доступа к SQL-таблицам Stream 3.
> Взаимодействие — исключительно через IntegrationEvent через Publisher.

---

## 11. Implementation Plan — Phase 1

### Step 1: Foundation (новые файлы)

| # | Файл | Что |
|---|------|-----|
| 1 | `backend/core/integration_event.py` | `IntegrationEvent` dataclass, `from_domain_event()` |
| 2 | `backend/core/event_registry.py` | `ensure_event_registry()` — единая точка регистрации |
| 3 | `backend/models/event_outbox.py` | SQLAlchemy model для `event_outbox` |
| 4 | `backend/models/business_events.py` | SQLAlchemy model для `business_events` |
| 5 | `backend/repositories/outbox_repository.py` | `OutboxRepository` — enqueue, fetch_pending, mark_published, mark_failed |
| 6 | `backend/repositories/event_repository.py` | `EventRepository` — append, replay |

### Step 2: Publisher

| # | Файл | Что |
|---|------|-----|
| 7 | `backend/infrastructure/event_publisher.py` | Publisher — polling loop, retry, backoff |
| 8 | `backend/infrastructure/consumer_base.py` | Base consumer with dedup + retry |

### Step 3: Integration

| # | Изменение | Что |
|---|-----------|-----|
| 9 | `backend/main.py` | `ensure_event_registry()`. Publisher background task |
| 10 | `backend/api/routes/agent.py` | Удалить `_register_event_handlers()` |
| 11 | `backend/services/document_lifecycle.py` | Добавить outbox enqueue в `mark_document_ready()` |
| 12 | `backend/services/...` (ClientService etc.) | Добавить outbox enqueue (по аналогии) |

### Step 4: Migration

| # | Что | Когда |
|---|-----|-------|
| 13 | GraphSync consumer → IntegrationEvent | После publisher |
| 14 | DomainEventBus removal plan | После миграции всех consumers |
| 15 | Clean up stale outbox records | После подтверждения at-least-once |

---

## 12. Exit Criteria

После завершения Phase 1 система гарантирует:

| ✓ | Что гарантируется |
|---|-------------------|
| ✓ | Event Envelope определён как единый формат (`IntegrationEvent`) |
| ✓ | Outbox запись создаётся в той же транзакции что и save |
| ✓ | Publisher доставляет события at-least-once |
| ✓ | Consumer контракт определён (consume → Result) |
| ✓ | Consumer идемпотентен (dedup по event_id) |
| ✓ | Retry policy: exponential backoff, max 3, dead letter |
| ✓ | P8 fix: единый registry, handler'ы не дублируются |
| ✓ | P10 fix: `aggregate_id` стабильный + `event_id` уникальный, без `entity_id` |
| ✓ | Тесты покрывают: outbox, publisher, consumer, replay |
| ✓ | Replay: deterministic, from_timestamp, from_sequence |

При этом система НЕ гарантирует:

| ✗ | Что НЕ гарантируется | Когда будет |
|---|----------------------|-------------|
| ✗ | Event Sourcing | ADR-030 — сознательно исключено |
| ✗ | CQRS projections | Stream 4+ |
| ✗ | Kafka/RabbitMQ | Post-MVP (абстракция publisher'а) |
| ✗ | Exactly-once delivery | Сознательно — at-least-once + idempotency достаточно |
| ✗ | Metrics/monitoring | Post-MVP |
| ✗ | Snapshot-based recovery | Stream 4+ |

---

*Документ создан 2026-07-26. Phase 1 — Design Proposal: Stream 3 Event Backbone.*
*Источники: current-event-backbone.md (Phase 0), ADR-030, Architecture Freeze,*
*Architecture Review Stream 3, backend/core/*, backend/services/*, Stream 0 proposal.*
