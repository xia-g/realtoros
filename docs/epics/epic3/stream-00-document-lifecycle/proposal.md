---
title: "Phase 1 — Design Proposal: Stream 0 Document Lifecycle Completion"
status: Approved
date: 2026-07-26
author: RealtorOS Architecture
---

# Phase 1 — Design Proposal: Stream 0 (Document Lifecycle Completion)

> **Описание:** Завершение lifecycle документа до READY: фиксация контрактов,
> валидации, событий и тестов на существующей инфраструктуре.
>
> **Discovery:** `current-lifecycle.md` (Phase 0, 175 строк).
>
> **Исходники:** `backend/services/document_lifecycle.py`, `backend/core/domain_events.py`,
> `backend/api/routes/documents.py`, `backend/tests/integration/test_document_lifecycle_api.py`.

---

## 1. Scope

### Добавляем

| Что | Где | Описание |
|-----|-----|----------|
| Завершение lifecycle до `READY` | `mark_document_ready()` | Use-case уже существует. Фиксируем контракт: allowed precursors, payload, event emission. |
| Семантические guard'ы | `mark_document_ready()` | Только `ANALYZED` или `NEEDS_REVIEW` → `READY`. Всё остальное — ошибка. |
| Idempotency guard | `mark_document_ready()` | Если `doc.status == "READY"` — возвращаем ошибку, статус не меняем, событие не эмитим. |
| Audit | `mark_document_ready()` | Фиксируем бизнес-действие `'READY transition accepted'`, а не просто `'status changed'`. Используем `logger.info('document_marked_ready', ...)`. |
| Test matrix | Тесты (domain + API) | Определяем минимальный набор сценариев (см. §5). |

### Не меняем

| Сущность | Причина |
|----------|---------|
| `Document` dataclass | Не расширяем API модели. |
| `status` как `str` | Без enum (см. Decision 2). |
| `DomainEventBus` singleton | Без outbox, без replay, без publisher. |
| `DocumentRepository` (sync psycopg2) | Без connection pool, без async. |
| `POST /{id}/transition` | Не открываем `READY` в generic transition — только через `/mark-ready`. |
| `POST /upload` | Не добавляем `document.created` event (см. §6). |

---

## 2. Decision Log

### Decision 1: Не превращаем Document в Aggregate

**Решение:** Document остаётся `@dataclass`. Все операции — через свободные функции.

**Причина:** Превращение Document в полноценный Aggregate потребует:

- Переноса методов `transition_document()`, `mark_document_ready()` в класс
- Изменения Repository (load/save целого aggregate)
- Добавления event-sourcing или, как минимум, domain events на каждую мутацию
- Согласования со всей upstream-инфраструктурой

Volume изменений неоправданно велик для Stream 0. Если потребуется, будет
отдельный ADR в одном из следующих Stream.

**Статус:** Accepted.

### Decision 2: Не вводим enum статусов

**Решение:** `status` остаётся `str`. Не добавляем `StrEnum`, `Literal` или Pydantic schema.

**Причина:** Замена `str` на enum затронет ~15 файлов — все ветвления `if doc.status == "READY"`,
все тесты, сериализацию, схему БД. Это механическая инженерия без семантической выгоды
для Stream 0. Если статусов станет >15 или появятся cross-entity state машины —
пересмотрим.

**Статус:** Accepted.

### Decision 3: Свободные функции, не методы

**Решение:** `mark_document_ready()` — свободная функция. Новые use-case'ы (если появятся)
должны следовать тому же паттерну.

**Причина:** Консистентность с существующим кодом (`transition_document()`,
`validate_transition()`). Паттерн работает: функция принимает `(doc, ...)`, мутирует
`doc` in-place, возвращает `(error, event)`. Изменение стиля только для READY сломает
единообразие кодовой базы.

**Статус:** Accepted.

---

## 3. Lifecycle Contract — READY

### Полный путь до READY

```
UPLOADED → VALIDATED → ACCEPTED → PROCESSING → ANALYZED → READY
                                                          ↑
                                              NEEDS_REVIEW ┘
```

### Матрица валидации — ANALYZED/NEEDS_REVIEW → READY

| From | To | Allowed | Reason |
|------|----|---------|--------|
| `ANALYZED` | `READY` | ✅ | Стандартный путь после OCR + анализа |
| `NEEDS_REVIEW` | `READY` | ✅ | После ручной проверки — документ готов |
| `READY` | `READY` | ❌ | Idempotent guard — ошибка, статус не меняется |
| `OCR_COMPLETED` | `READY` | ❌ | Такого статуса нет в модели — только через `ANALYZED` |
| `FAILED` | `READY` | ❌ | Только через retry (`FAILED → PROCESSING → ... → ANALYZED`) |
| `UPLOADED` | `READY` | ❌ | Слишком рано — документ не прошёл ни одной стадии |
| `PROCESSING` | `READY` | ❌ | Только через `ANALYZED` |

### Инвариант READY

Инвариант: документ в состоянии **READY** считается **полностью обработанным**
и готовым к использованию другими bounded contexts.

Это означает:
- анализ завершён
- OCR завершён
- метаданные существуют
- документ больше не изменяется

**READY — контракт для downstream:** Business Events, Knowledge, Accounting, Deal Resolution.

### Выбор варианта идемпотентности

Выбран **вариант A**: повторный `READY` → `409 Conflict`, статус не меняется, событие не эмитится.

**Вариант B** (`200 OK`, без события) осознанно отклонён:
для событийной архитектуры семантически правильнее сообщить
клиенту, что действие уже выполнено, а не маскировать идемпотентность.

### Guard'ы в `mark_document_ready()` (код)

```python
# 1. Idempotency guard
if doc.status == "READY":
    return "Document is already in READY state", None

# 2. Semantic guard — только ANALYZED или NEEDS_REVIEW
ALLOWED_PRECURSORS = {"ANALYZED", "NEEDS_REVIEW"}
if doc.status not in ALLOWED_PRECURSORS:
    return f"Cannot transition from {doc.status} to READY: ...", None

# 3. VALID_TRANSITIONS guard (через transition_document())
err = transition_document(doc, "READY")
if err:
    return err, None
```

---

## 4. Event Contract — `DocumentReady`

### DomainEvent dataclass (существующий)

```python
@dataclass
class DomainEvent:
    event_type: str
    entity_type: str
    entity_id: UUID
    actor_id: str = "system"
    correlation_id: str = ""
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### Payload для `document.ready`

```json
{
  "event_type": "document.ready",
  "entity_type": "document",
  "entity_id": "<UUID>",
  "actor_id": "<system|user_id>",
  "correlation_id": "",
  "occurred_at": "<ISO-8601 UTC>",
  "payload": {
    "status": "READY",
    "previous_status": "ANALYZED|NEEDS_REVIEW",
    "document_id": "<str>",
    "organization_id": "<str>",
    "contract_number": "<str>",
    "total_price": "<str>",
    "buyer_name": "<str>",
    "seller_name": "<str>",
    "profile": { }
  }
}
```

### Что НЕ входит

- **Publisher URL** — нет outbox, нет replay, нет внешней публикации
- **Version** — нет схемы event versioning (пока не требуется)
- **Aggregate root ID** — Document не aggregate

### Механизм эмиссии

```python
bus = event_bus or get_event_bus()
try:
    loop = asyncio.get_running_loop()
    loop.create_task(bus.emit(event))
except RuntimeError:
    # No running loop — log and continue
    logger.warning("no_event_loop", event_type=EVENT_DOCUMENT_READY)
```

Stream 0 опирается на существующий механизм доставки событий
(DomainEventBus + loop.create_task()) и **НЕ гарантирует надёжную доставку**.
Это **осознанное архитектурное ограничение**.

План устранения: Stream 3 (Business Events) введёт Event Backbone
с append-only логом, durable delivery и at-least-once гарантиями.

### Delivery Guarantees

| Stream | Гарантия | Тип |
|--------|----------|-----|
| **Stream 0** | Best effort · At-most-once · in-process only | Текущая реализация |
| **Stream 3** (будущий) | Append-only · Durable · Replayable · At-least-once | Event Backbone |

---

## 5. Test Matrix

### Domain unit tests (`test_document_lifecycle_domain.py`)

| # | Сценарий | Input | Expected |
|---|----------|-------|----------|
| 1 | ANALYZED → READY успешно | `doc.status="ANALYZED"` | `(None, DomainEvent)`; `doc.status == "READY"` |
| 2 | NEEDS_REVIEW → READY успешно | `doc.status="NEEDS_REVIEW"` | `(None, DomainEvent)`; `doc.status == "READY"` |
| 3 | READY дважды (idempotency) | `doc.status="READY"` | `("Document is already in READY state", None)`; статус не меняется |
| 4 | UPLOADED → READY (invalid) | `doc.status="UPLOADED"` | `(error_message, None)` |
| 5 | FAILED → READY (invalid) | `doc.status="FAILED"` | `(error_message, None)` |
| 6 | Event создаётся ровно один раз | ANALYZED → READY | `event.event_type == "document.ready"`; `event.payload["previous_status"] == "ANALYZED"` |

### API integration tests (расширить `test_document_lifecycle_api.py`)

| # | Сценарий | HTTP | Expected |
|---|----------|------|----------|
| 1 | ANALYZED → /mark-ready → 200 | `POST /{id}/mark-ready` | 200; `status == "READY"`; `event_id` и `event_type` в ответе |
| 2 | NEEDS_REVIEW → /mark-ready → 200 | `POST /{id}/mark-ready` | 200; `status == "READY"` |
| 3 | Document not found | `POST /nonexistent/mark-ready` | 404 |
| 4 | Already READY (idempotency) | дважды `POST /{id}/mark-ready` | 1-й: 200. 2-й: **409 Conflict** (сейчас 400 — см. §6 Technical Debt) |
| 5 | Invalid transition (UPLOADED → READY) | `POST /{id}/mark-ready` | **422 Unprocessable Entity** (сейчас 400 — см. §6 Technical Debt) |
| 6 | Audit log | проверить structlog output | `document_marked_ready` запись с `document_id`, `actor_id` |

**Примечание:** Существующие тесты покрывают сценарии 1, 2, 3, 4 и 6 частично.
Сценарий 5 тестируется (test_mark_ready_from_wrong_state). Основная разница —
HTTP status codes (см. Technical Debt).

---

## 6. Technical Debt (из Phase 0 findings)

### Не блокируют Stream 0 (зафиксировать, не исправлять)

| Проблема | Где | Почему не блокирует |
|----------|-----|---------------------|
| `status` как `str` | Везде | Без enum — осознанное решение (Decision 2) |
| Document не aggregate | `document_lifecycle.py` | Не требуется для завершения lifecycle (Decision 1) |
| Repository без connection pool | `DocumentRepository` | Stream 0 не пишет новые запросы к БД |
| `POST /{id}/mark-ready` возвращает 400 вместо 409/422 | `api/routes/documents.py:223` | Статус-код не меняет семантику. Если Stream 3 начнёт читать 409 — исправить отдельно |
| `EVENT_DOCUMENT_CREATED` / `EVENT_DOCUMENT_DELETED` не эмитятся | `domain_events.py` | Определены, но не реализованы. Не мешают READY |
| Отсутствует delete endpoint | `api/routes/documents.py` | Не входит в scope Stream 0 |

### Требуют отдельной оценки

| Проблема | Описание | Рекомендация |
|----------|----------|--------------|
| `DomainEventBus.emit()` — async из sync-контекста | `mark_document_ready()` использует `asyncio.get_running_loop().create_task()` | Если DocumentReady станет отправной точкой событийной архитектуры (Stream 3), этот механизм нужно заменить на надёжный (outbox/explicit queue). В Stream 0 не переписываем. |
| Lazy import psycopg2 внутри каждого метода Repository | `psycopg2` импортируется локально в `_connect()`, `save()`, `get()` и т.д. | Не влияет на корректность, но нестандартно. Рефакторинг — если Repository переписывается в async. |
| `entity_id` в DomainEvent — новый UUID, не document_id | `mark_document_ready()` создаёт `uuid.uuid4()` для `entity_id` | Сейчас не критично — событие не используется для идентификации документа. При переходе к event-архитектуре — исправить на `doc.document_id`. |

### Сознательно не входит в scope

- `document.created` event — не расширяем scope. Константа `EVENT_DOCUMENT_CREATED` существует,
  но не эмитится. Это не мешает завершению lifecycle документа.
- Удаление / рефакторинг `test_8_transition_ready` (переход через generic `/transition`) —
  тест использует `POST /{id}/transition` с `target_status="READY"`, что работает через
  `transition_document()` напрямую, минуя `mark_document_ready()`. Это legacy-тест,
  не влияет на новый функционал. Удалить или переписать при следующем рефакторинге тестов.

---

## 7. Exit Criteria

После завершения Stream 0 система гарантирует:

| ✓ | Что гарантируется |
|---|-------------------|
| ✓ | `READY` достигается только валидным переходом (`ANALYZED` или `NEEDS_REVIEW` → `READY`) |
| ✓ | `READY` не может быть выполнен дважды (idempotency guard — 409 Conflict) |
| ✓ | `document.ready` публикуется один раз |
| ✓ | API покрыт тестами (domain + integration) |
| ✓ | lifecycle полностью протестирован |

При этом система ещё **НЕ** гарантирует:

| ✗ | Что НЕ гарантируется | Когда будет |
|---|----------------------|-------------|
| ✗ | durable delivery | Stream 3 (Business Events) |
| ✗ | replay | Stream 3 (Business Events) |
| ✗ | outbox | Stream 3 (Business Events) |
| ✗ | append-only event log | Stream 3 (Business Events) |
| ✗ | consumers | Stream 3+ |
