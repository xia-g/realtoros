# Current Document Lifecycle — Stream 0 Discovery

> **Phase 0 (Architecture Discovery).**  
> No code changes. Honest snapshot of the existing Document Lifecycle as of July 2026.

---

## 1. Где живёт Document Aggregate

**Файл:** `backend/services/document_lifecycle.py`

**Тип:** `@dataclass` — не entity, не aggregate, не value object. Чистый data holder.

**Поля:**

| Группа | Поля |
|---|---|
| Идентификация | `document_id`, `organization_id` |
| Аудитория | `uploaded_by`, `uploaded_at` |
| Lifecycle | `status` (str), `pipeline_stage` (str) |
| Файл | `storage_uri`, `mime_type`, `page_count`, `size_bytes`, `checksum`, `original_filename` |
| Product | `metadata` (dict — до анализа), `profile` (dict — после анализа) |
| DB | `created_at`, `updated_at` |

**Почему это не aggregate:**
- Нет методов — все операции вынесены в свободные функции вне класса
- `status` — просто `str`, нет enum/типизированного union/a
- Нет инвариантов: Document не проверяет своё состояние при создании или мутации
- Нет защиты: любая внешняя функция может поменять `doc.status` напрямую, минуя `transition_document()`

---

## 2. Существующий Lifecycle (состояния и переходы)

**10 статусов, определённых в `VALID_TRANSITIONS`:**

```
UPLOADED ──→ VALIDATED ──→ ACCEPTED ──→ PROCESSING ──→ ANALYZED ──→ READY ──→ ROUTED ──→ ARCHIVED
   │             │             │              │               │          │           │
   └──→ REJECTED └──→ REJECTED └──→ FAILED └──→ FAILED      └──→ NEEDS_REVIEW
                                                    │               │
                                                    └──→ NEEDS_REVIEW └──→ PROCESSING
                                                                         └──→ READY
                                                                         └──→ ARCHIVED

FAILED ──→ PROCESSING (retry)
```

**Матрица переходов:**

| From \ To | VALIDATED | REJECTED | ACCEPTED | PROCESSING | FAILED | ANALYZED | NEEDS_REVIEW | READY | ROUTED | ARCHIVED |
|---|---|---|---|---|---|---|---|---|---|---|
| **UPLOADED** | ✓ | ✓ | | | | | | | | |
| **VALIDATED** | | ✓ | ✓ | | | | | | | |
| **ACCEPTED** | | | | ✓ | ✓ | | | | | |
| **PROCESSING** | | | | | ✓ | ✓ | ✓ | | | |
| **ANALYZED** | | | | | | | ✓ | ✓ | | |
| **READY** | | | | | | | | | ✓ | |
| **ROUTED** | | | | | | | ✓ | | | ✓ |
| **ARCHIVED** | | | | | | | | | | |
| **REJECTED** | | | | | | | | | | |
| **FAILED** | | | | ✓ | | | | | | |
| **NEEDS_REVIEW** | | | | ✓ | | | | ✓ | | ✓ |

**Terminal states:** `ARCHIVED`, `REJECTED`.

**Замечание:** `NEEDS_REVIEW` не terminal — из него можно выйти в PROCESSING, READY или ARCHIVED. Это "рецензионный тупик", а не конец жизненного цикла.

---

## 3. Где выполняются переходы

Все lifecycle-операции — **свободные функции**, а не методы Document.

### `transition_document(doc, target)` — базовая функция
- Валидирует переход через `VALID_TRANSITIONS`
- Проверяет `TERMINAL_STATES`
- Мутирует `doc.status` и `doc.updated_at` in-place
- Используется напрямую из API-роутов и из `mark_document_ready()`

### `mark_document_ready(doc, actor_id, event_bus)` — use case
- Проверяет семантический guard: только `ANALYZED` или `NEEDS_REVIEW` → `READY`
- Вызывает `transition_document()`
- Собирает payload (profile, contract_number, prices, имена сторон)
- Создаёт и эмитит `DomainEvent` (`EVENT_DOCUMENT_READY`)
- Пишет audit-log через structlog

### API endpoints (`backend/api/routes/documents.py`)

| Endpoint | Действие | Начальный статус | Конечный статус |
|---|---|---|---|
| `POST /upload` | Загрузить файл | — | UPLOADED |
| `POST /{id}/transition` | Любой валидный переход | Любой (кроме terminal) | Любой (кроме READY) |
| `POST /{id}/mark-ready` | Специализированный READY | ANALYZED / NEEDS_REVIEW | READY |
| `GET /{id}` | Чтение | — | — |
| `GET /{id}/status` | Статус + allowed transitions | — | — |
| `GET /list` | Список (фильтр по status) | — | — |

**Замечание:** `POST /{id}/transition` не принимает `READY` как `target_status` — для READY есть отдельный `/mark-ready` с эмиссией события. Это архитектурное решение, не случайность.

---

## 4. Существующие события

**Файл:** `backend/core/domain_events.py`

### DomainEventBus
- Sync singleton (с инициализацией через `get_event_bus()`)
- `register(event_type, handler)` — подписка
- `emit(event)` — async метод; handler'ы вызываются последовательно
- `register_all(handlers_dict)` — групповая регистрация

### Зарегистрированные константы event_type (для документов):
```python
EVENT_DOCUMENT_CREATED = "document.created"
EVENT_DOCUMENT_DELETED = "document.deleted"
EVENT_DOCUMENT_READY   = "document.ready"
```

### Формат `DomainEvent` (dataclass):
```python
@dataclass
class DomainEvent:
    event_type: str
    entity_type: str
    entity_id: UUID
    actor_id: str = "system"
    correlation_id: str = ""
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=...)
```

**Замечание:** На данный момент только `EVENT_DOCUMENT_READY` реально эмитится (в `mark_document_ready()`). Константы `EVENT_DOCUMENT_CREATED` и `EVENT_DOCUMENT_DELETED` определены, но их эмиссия не реализована ни в upload, ни в delete-логике (delete endpoint отсутствует).

---

## 5. Repository

**Файл:** `backend/services/document_lifecycle.py` (класс `DocumentRepository`)

- **Тип:** sync psycopg2 (не async)
- **Слой:** Product Layer (явно указано в docstring)
- **Таблица:** `document_intake`
- **Методы:**
  - `save(doc)` — INSERT ... ON CONFLICT (document_id) DO UPDATE (upsert)
  - `get(document_id)` — SELECT с RealDictCursor, собирает Document
  - `list_by_status(status)` — фильтр по status
  - `update_status(document_id, status, stage)` — get + transition_document + save

**Замечание:** Repository использует lazy import (`import psycopg2` внутри каждого метода), что нестандартно. Подключение создаётся на каждый вызов — нет connection pool.

---

## 6. Выводы для Stream 0

### Что уже готово
- Полный граф из 10 состояний с валидными переходами
- Функция `transition_document()` с валидацией
- Use case `mark_document_ready()` с эмиссией события
- DomainEventBus (sync singleton, async emit)
- Три event-константы для документов
- Repository с CRUD (`document_intake` table)
- 6 API endpoints

### Что отсутствует / может потребоваться
- **Нет event `document.created`**: создание документа в `POST /upload` не эмитит событие
- **Нет delete endpoint**: `EVENT_DOCUMENT_DELETED` определён, но API-ручки нет
- **No enum for status**: `status` — `str`, возможны опечатки; нет ни Literal, ни StrEnum, ни валидации схемы на уровне Pydantic/FastAPI
- **Нет aggregate guard**: любая функция может установить `doc.status = "INVALID"` напрямую, минуя `transition_document()`
- **DomainEventBus sync, emit async**: `mark_document_ready()` использует `asyncio.get_running_loop().create_task()` для эмиссии из синхронного контекста — хрупкий паттерн (упадёт, если нет running loop, хотя fallback на log есть)
- **Repository без connection pool**: каждое подключение — новый psycopg2 connect
- **Только один тип событий эмитится реально**: `document.ready`

### Как `mark_document_ready()` вписывается в стиль
Вписывается органично — это свободная функция, как и `transition_document()`. Отличие: у неё два return значения `(error, event)`, в то время как `transition_document()` возвращает `str | None`. Если добавлять новые специализированные переходы (например, `mark_document_routed()`), стоит следовать тому же паттерну: свободная функция, семантический guard, эмиссия события.
