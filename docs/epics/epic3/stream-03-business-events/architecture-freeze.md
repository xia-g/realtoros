---
status: Frozen
date: 2026-07-24
author: Architect (RealtorOS)
version: 1.0.0
context: Epic 3 — Accounting Compliance & Reporting | Stream 3 — Business Events
predecessor: Epic3-Foundation-Checkpoint.md (Stream 1 — Organization Profile)
---

# Stream 3 — Business Events: Architecture Freeze Record

> Настоящий документ фиксирует архитектурные решения Stream 3, принятые после approval Proposal и ADR-030. Все перечисленные ниже решения являются **Frozen** — их изменение требует нового ADR. Документ не описывает «почему» (это в proposal и ADR), а только **что зафиксировано** и **какие контракты immutable**.

---

## 1. Purpose

После approval Proposal Stream 3 (Architecture Review v3.0) **замороженными считаются**:

- Единая событийная модель Compliance Platform (BusinessEvent / EventEnvelope)
- Append-only логика записи и хранения событий
- Transactional Outbox как единственный механизм публикации
- At-least-once семантика доставки с идемпотентными Consumer'ами
- FIFO ordering per aggregate (organization_id)
- Replay модель для восстановления состояния Consumer'ов
- Cross-stream контракты: только BusinessEvent/EventEnvelope через Event Backbone
- Repository-интерфейсы (IEventRepository, IOutboxRepository, IEventBroker)

**Не frozen** (могут эволюционировать без ADR):
- Конкретная реализация SQLAlchemy-репозиториев
- Outbox Publisher polling interval, batch_size, backoff-параметры
- Реализация парсеров в EventSchemaRegistry
- Конкретный брокер (RabbitMQ / Kafka / Redis Streams)
- API endpoint format и Pydantic-схемы (пока не нарушают domain)

---

## 2. Frozen Decisions

| # | Decision | Reference | Status |
|:-:|:---------|:----------|:-------|
| D1 | **Append-only Log** — единственная операция записи: INSERT. Никаких UPDATE/DELETE. Отмена — только через компенсирующие события | ADR-030, ADR-001 | ✅ Frozen |
| D2 | **Transactional Outbox** — запись в append-only журнал и публикация в брокер атомарны (одна транзакция). Outbox — единственный путь публикации | Proposal §4 | ✅ Frozen |
| D3 | **At-least-once Delivery** — событие доставлено минимум один раз. Дубликаты отфильтровываются Consumer'ом по event_id | Proposal §8 | ✅ Frozen |
| D4 | **FIFO per Aggregate** — события одного AggregateId (organization_id) упорядочены по sequence_number. Глобальный порядок не гарантируется | Proposal §6 | ✅ Frozen |
| D5 | **Replay Model** — штатный механизм восстановления состояния Consumer'а. Поддерживает: truncate+full, partial (gap recovery), batch with checkpoints, parallel per-aggregate | Proposal §7 | ✅ Frozen |
| D6 | **Event Envelope** — BusinessEvent (event_id, event_type, metadata, correlation_id, causation_id, aggregate_id, sequence, payload) + EventMetadata + EventPayload. Трёхслойная структура: Identity → Envelope → Payload | Proposal §2.4–2.5 | ✅ Frozen |
| D7 | **Cross-stream Contracts** — downstream Streams получают события только через BusinessEvent/EventEnvelope, НЕ через прямой SQL-доступ к таблицам Stream 3 | Proposal §9.10 | ✅ Frozen |

---

## 3. ADR References

| ADR | Title | Relation |
|:----|:------|:---------|
| ADR-017 | BusinessEvent taxonomy and hierarchy | Определяет EventType enum, иерархию `accounting.*` / `compliance.*`, правила добавления новых типов |
| ADR-018 | Event schema versioning strategy | Определяет schema_version в EventMetadata, VersionedSchema Registry, backward/breaking compatibility rules |
| ADR-030 | Append-only Event Log vs Event Sourcing | Выбор модели: append-only log + отдельное текущее состояние (НЕ full event sourcing) |

> **Примечание:** ADR-017 и ADR-018 приняты на уровне архитектурного решения, но их текст может быть формализован как часть Stream 3 delivery. Их ключевые положения уже зафиксированы в proposal (§2.2 EventType, §5 Event Versioning) и frozen данным документом.

---

## 4. Immutable Contracts

### 4.1 BusinessEvent

```python
@dataclass(frozen=True)
class BusinessEvent:
    event_id: EventId                  # UUID v7, глобально уникальный
    event_type: EventType              # "accounting.period_closed" | "compliance.eligibility_determined" | ...
    metadata: EventMetadata            # source, schema_version, created_at, created_by, producer
    correlation_id: CorrelationId      # группировка связанных событий
    causation_id: CausationId          # ссылка на причину (EventId | None)
    aggregate_id: AggregateId          # = organization_id
    sequence: EventSequence            # монотонный номер внутри AggregateId
    payload: EventPayload              # только доменные данные
    compensates_event_id: EventId | None = None
```

**Invariants:**
- `frozen=True` — никогда не изменяется после создания
- Единственная операция: INSERT в append-only журнал
- sequence_number строго монотонный внутри AggregateId
- НЕТ поля `status` — статус доставки принадлежит Outbox, не домену

### 4.2 EventMetadata

```python
@dataclass(frozen=True)
class EventMetadata:
    source: str                        # "accounting" | "compliance" | "import"
    schema_version: int = 1            # версия схемы payload
    created_at: datetime               # время создания (из Clock)
    created_by: str = "system"         # кто создал событие
    producer: str = "compliance"       # имя сервиса-производителя
```

**Invariant:** EventMetadata содержит **только инфраструктурные и транспортные поля**. Никаких доменных данных.

### 4.3 EventPayload Boundary

```python
@dataclass(frozen=True)
class EventPayload:
    event_type: EventType
    organization_id: UUID
    period: str                        # "2026-Q1", "2026-06", "2025"
    data: dict[str, Any]               # бизнес-данные события
```

**Правило границы:** Payload содержит **исключительно доменные данные**. Инфраструктурные поля (producer, broker metadata, ORM identifiers) — строго в EventMetadata. schema_version определяет формат data.

### 4.4 IEventRepository

```python
class IEventRepository(ABC):
    async def append(self, event: BusinessEvent) -> None
    async def append_batch(self, events: list[BusinessEvent]) -> None
    async def next_sequence(self, aggregate_id: AggregateId) -> EventSequence
    async def get_event(self, event_id: EventId) -> BusinessEvent | None
    async def replay_by_aggregate(self, aggregate_id: AggregateId,
                                  from_sequence: int = 1,
                                  to_sequence: int | None = None,
                                  limit: int = 1000,
                                  offset: int = 0) -> list[BusinessEvent]
    async def replay_by_type(self, event_type: EventType,
                             from_date: datetime | None = None,
                             to_date: datetime | None = None,
                             limit: int = 1000,
                             offset: int = 0) -> list[BusinessEvent]
    async def count_events(self, aggregate_id: AggregateId) -> int
    async def get_events_by_correlation(self, correlation_id: UUID) -> list[BusinessEvent]
```

**Invariants:** НЕТ update/delete. НЕТ commit() — транзакция в Application Service. sequence_number монотонный внутри AggregateId.

### 4.5 IOutboxRepository

```python
class IOutboxRepository(ABC):
    async def enqueue(self, event: BusinessEvent) -> None
    async def fetch_pending(self, limit: int = 100) -> list[OutboxItem]
    async def mark_published(self, outbox_id: UUID) -> None
    async def mark_failed(self, outbox_id: UUID, error: str) -> None
    async def fetch_failed(self, max_retries: int = 3, limit: int = 100) -> list[OutboxItem]
    async def retry(self, outbox_id: UUID) -> None
```

**Invariant:** Outbox работает в той же транзакции, что и IEventRepository.append(). Статусы: `pending` → `published` | `failed` | `dead_letter`.

---

## 5. Accepted Technical Debt

| # | Item | Rationale | Target |
|:-:|:-----|:----------|:-------|
| T1 | **`event_type_version` отсутствует** — используется `metadata.schema_version` как единый счётчик версий | Schema_version покрывает все изменения payload. Выделенный event_type_version избыточен при текущей модели | Не планируется — сознательное упрощение |
| T2 | **Concurrent sequence retry** — описан на уровне архитектуры, но реализация отложена | В текущей модели sequence_number вычисляется как MAX+1. При конкурентной вставке возможен конфликт UNIQUE constraint | Deferred — реализация при нагрузочном тестировании |
| T3 | **Optimistic locking** — не реализован в Stream 3 | Stream 3 — append-only, нет UPDATE. Optimistic locking потребуется для Consumer'ов (Stream 4+), которые обновляют состояние | Stream 4+ |
| T4 | **Snapshot** — механизм snapshot-based recovery не входит в Stream 3 | Snapshot ускоряет replay для Consumer'ов с длинной историей. Для Stream 3 (append-only журнал) snapshot не имеет смысла | Stream 4 (Compliance State) |
| T5 | **Metrics** — instrumentation и мониторинг не вошли в Stream 3 | Outbox Publisher, replay latency, event throughput — метрики deferred до появления эксплуатационных требований | Post-MVP |

---

## 6. Explicit Non-goals

| # | Non-goal | Rationale |
|:-:|:---------|:----------|
| N1 | **Full Event Sourcing** — события НЕ являются единственным источником истины для агрегатов | ADR-030: выбрана модель Append-only Log + отдельное текущее состояние. Full ES — overengineering для Compliance |
| N2 | **Kafka dependency** — конкретный брокер не выбран | IEventBroker — абстракция. Реализация (RabbitMQ / Kafka / Redis Streams) выбирается на этапе инфраструктуры |
| N3 | **Exactly Once delivery** — не поддерживается | At-least-once + идемпотентные Consumer'ы достаточно для Compliance. Exactly-once требует distributed transactions |
| N4 | **Distributed transactions** — Outbox единственная транзакция | Никаких 2PC, Saga, XA. Только локальная PostgreSQL транзакция для append + outbox |
| N5 | **Snapshot-based recovery** — отложено до Stream 4 | Stream 3 хранит сырые события. Snapshot — ответственность Consumer'а (Stream 4 — Compliance State) |

---

## 7. ADR Trigger Matrix

| Изменение | Требует ADR | Комментарий |
|:----------|:------------|:------------|
| Новый lifecycle события (новый EventType) | ✅ | Необходимо обновить EventType enum и зарегистрировать в COMPENSATING_EVENTS |
| Изменение delivery semantics (at-least-once → exactly-once) | ✅ | Меняет фундаментальную гарантию для всех Streams |
| Новый transport (добавление брокера) | ❌ | IEventBroker — абстракция; новая реализация не меняет контракт |
| Новый consumer (новый Stream) | ❌ | Event Backbone спроектирован для произвольного числа Consumer'ов |
| Замена append-only на mutable storage | ✅ | Нарушает ADR-030, ADR-001, все инварианты |
| Изменение Event Envelope (BusinessEvent / EventMetadata / EventPayload) | ✅ | Меняет контракт для всех downstream Streams |
| Новый replay strategy | ⚠️ Возможно | Если не нарушает существующие гарантии детерминизма — не требуется |
| Изменение Outbox механизма (Transactional → polling-only) | ✅ | Меняет гарантию атомарности записи |
| Добавление snapshot-based recovery | ⚠️ Возможно | Только если меняет replay модель (checkpoint, truncate семантику) |
| Добавление metrics/monitoring | ❌ | Инфраструктурное улучшение, не затрагивает архитектуру |
| Изменение CompensatingEvent registry | ❌ | Добавление новых пар — эволюция, не нарушение контракта |
| Удаление существующего EventType | ✅ | Breaking change для Consumer'ов |

---

## 8. Stream Dependencies

Ниже перечислено, что каждый downstream Stream (4–11) потребляет от Stream 3 и какие гарантии контракта для него frozen.

### Stream 4 — Compliance State

| Аспект | Значение |
|:-------|:---------|
| **Потребляет** | Все события (BusinessEvent) |
| **Контракт** | ordered per org, at-least-once, replay-capable |
| **Replay** | `replay_by_aggregate()` — полное восстановление состояния |
| **Dedup** | По event_id (processed_events таблица) |

### Stream 5 — Eligibility Engine

| Аспект | Значение |
|:-------|:---------|
| **Потребляет** | Фильтр по EventType (`compliance.eligibility_determined` + триггерные события) |
| **Контракт** | ordered per org, cache-based (replay не используется) |
| **Dedup** | По event_id |

### Stream 6 — Dependency Engine

| Аспект | Значение |
|:-------|:---------|
| **Потребляет** | Фильтр по EventType (period_closed, payroll_posted, ...) |
| **Контракт** | ordered per org + replay |
| **Replay** | `replay_by_type()` — частичное восстановление зависимостей |
| **Dedup** | По event_id |

### Stream 7 — Simulation Engine

| Аспект | Значение |
|:-------|:---------|
| **Потребляет** | EventEnvelope (read-only доступ к полной истории) |
| **Контракт** | Replay с модифицированными payload'ами (counterfactual). Отдельная сессия — не влияет на live events |
| **Dedup** | N/A (отдельная сессия replay) |

### Stream 8 — Compliance Timeline

| Аспект | Значение |
|:-------|:---------|
| **Потребляет** | Accounting events (EventEnvelope, read-only) |
| **Контракт** | ordered per org, at-least-once |
| **Replay** | Не используется (строит timeline из live событий) |
| **Dedup** | По event_id |

### Stream 9 — Reporting Workspace

| Аспект | Значение |
|:-------|:---------|
| **Потребляет** | Через API Gateway — не напрямую из Event Backbone |
| **Контракт** | Stream 9 взаимодействует с событиями через REST API, не через брокер |

### Stream 10 — Task Model / Notifications

| Аспект | Значение |
|:-------|:---------|
| **Потребляет** | Compliance-события (EventEnvelope), failures, warnings |
| **Контракт** | at-least-once (допустимо пропустить дубликаты) |
| **Side effects** | Push-уведомления, email — защищены идемпотентностью |
| **Dedup** | По dedup_id |

### Stream 11 — Explainability API

| Аспект | Значение |
|:-------|:---------|
| **Потребляет** | Все события (EventEnvelope, read-only) |
| **Контракт** | Доступ к полному EventStream для построения ReasoningGraph |
| **Dedup** | N/A (read-only доступ) |

---

## 9. Summary

| Domain | Status |
|:-------|:-------|
| Append-only Log | ✅ Frozen (ADR-030) |
| Transactional Outbox | ✅ Frozen |
| At-least-once Delivery | ✅ Frozen |
| FIFO per Aggregate | ✅ Frozen |
| Replay Model | ✅ Frozen |
| Event Envelope | ✅ Frozen |
| Cross-stream Contracts | ✅ Frozen |
| Repository Interfaces | ✅ Frozen |
| Total Frozen Decisions | **7** |
| ADR References | ADR-017, ADR-018, ADR-030 |
| Accepted Technical Debt | 5 items |
| Explicit Non-goals | 5 items |
| ADR Triggers | 12 conditions |
| Downstream Streams | 8 (Streams 4–11) |

---

*Документ создан 2026-07-24. Версия 1.0.0.*
*Предыдущий checkpoint: Epic3-Foundation-Checkpoint.md (Stream 1 — Organization Profile).*
