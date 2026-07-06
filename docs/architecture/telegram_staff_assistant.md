# Telegram Staff Assistant V1 — Architecture

**Date:** 2026-06-07
**Sprint:** 3
**Status:** Draft
**Related ADR:** ADR-0014

---

## 1. Sprint 3 Goals

### What the bot MUST do
- Authenticate employees via Telegram ID
- Display role-based main menu
- View, search, filter, assign leads
- Qualify and convert leads (via CRM API)
- Create, view, search clients
- View client history (deals, properties, tasks, communications)
- Search properties by address, cadastre, owner
- View property card with documents and linked deals
- Create, assign, complete, reopen tasks (FSM wizard)
- View deals and change deal status
- Send notifications on new leads and task assignments

### What is NOT in Sprint 3
- Knowledge Agent integration
- AI-powered lead scoring
- Client-facing bot
- Document upload via bot
- Payment processing
- Report generation / analytics dashboard
- Webhook-driven real-time updates (polling only)

---

## 2. Architecture

### Layer Diagram

```
Telegram User (Employee)
    |
    | Telegram API (Long Polling / Webhook)
    v
+---------------------------------------+
|         Aiogram Dispatcher             |
|  Router | Middleware | FSM Storage     |
+---------------------------------------+
    |                                       |
    v                                       v
+------------------+          +-------------------------+
|  Auth Middleware  |          |  RequestContext MW       |
|  - verify role    |          |  - set source_component  |
|  - load user      |          |  - inject user_id        |
+------------------+          +-------------------------+
    |                                       |
    v                                       v
+---------------------------------------+
|      Router / Handler Layer            |
|  start.py    leads.py   clients.py     |
|  properties.py  deals.py  tasks.py     |
|  admin.py                              |
+---------------------------------------+
    |
    | httpx (async HTTP client)
    v
+---------------------------------------+
|         CRMClient Service              |
|  - GET/POST/PATCH/DELETE               |
|  - retry policy (3 attempts)           |
|  - timeout (10s connect, 30s read)     |
|  - error mapping -> user messages      |
+---------------------------------------+
    |
    | HTTP
    v
+---------------------------------------+
|         FastAPI Backend                 |
|  /api/v1/leads, /clients, /deals       |
|  /api/v1/properties, /tasks            |
+---------------------------------------+
    |
    v
+---------------------------------------+
|     CRM Service Layer + Repositories   |
+---------------------------------------+
```

### Data Flow

```
User sends /command
  -> aiogram dispatcher
    -> AuthMiddleware: check telegram_id in users table
      -> RequestContextMiddleware: inject user_id, source_component
        -> Handler: parse command, call CRMClient
          -> CRMClient: httpx request to FastAPI
            -> CRM Service: business logic + audit
              -> Repository: DB query
                -> Response flows back up as JSON
```

---

## 3. Folder Structure

```
bot/
+-- __init__.py
+-- app.py                    # Aiogram app factory + main()
+-- config.py                 # BOT_TOKEN, API_BASE_URL, ADMIN_IDS
|
+-- handlers/
|   +-- __init__.py
|   +-- start.py              # /start - auth gate, /menu
|   +-- leads.py              # Lead CRUD + lifecycle
|   +-- clients.py            # Client search, card, history
|   +-- properties.py         # Property search + card
|   +-- deals.py              # Deal list, card, status change
|   +-- tasks.py              # Task FSM create, complete, reopen
|   +-- admin.py              # Admin panel (admin only)
|
+-- keyboards/
|   +-- __init__.py
|   +-- main.py               # Main menu ReplyKeyboardMarkup
|   +-- leads.py              # Lead card InlineKeyboard
|   +-- clients.py            # Client card InlineKeyboard
|   +-- properties.py         # Property card InlineKeyboard
|   +-- tasks.py              # Task actions InlineKeyboard
|
+-- services/
|   +-- __init__.py
|   +-- crm_client.py         # CRMClient - httpx wrapper
|   +-- permissions.py        # Role/permission checks
|   +-- notifications.py      # Notification dispatcher + templates
|
+-- middleware/
|   +-- __init__.py
|   +-- auth.py               # AuthMiddleware - telegram_id check
|   +-- request_context.py    # Inject audit metadata
|
+-- states/
|   +-- __init__.py
|   +-- lead.py               # LeadCreate FSM (5 steps)
|   +-- task.py               # TaskCreate FSM (4 steps)
|   +-- property.py           # PropertyCreate FSM (future)
|
+-- schemas/
|   +-- __init__.py
|   +-- callbacks.py          # Typed callback data classes
|
+-- tests/
    +-- __init__.py
    +-- conftest.py
    +-- test_auth.py
    +-- test_handlers/
    +-- test_services/
    +-- test_keyboards/
```
## 4. Authentication

### /start Flow

User sends /start -> AuthMiddleware captures message.from_user.id -> CRMClient.get("/api/v1/users?telegram_id={tg_id}") -> Backend checks users.telegram_id -> Found: return User + role, show main menu -> 404: "Вы не авторизованы. Обратитесь к администратору."

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User deleted from CRM | Next /start: 404 "Доступ отозван" |
| Soft-deleted user | Auth rejects: "Ваша учетная запись деактивирована" |
| Role changed | Next /start loads fresh role, menu adjusts |
| No telegram_id set | User cannot authenticate until admin assigns |

### Session Cache
- Successful auth cached for 1 hour (in-memory dict)
- Reduces API calls on every update
- Cleared on /logout or role change detection

---

## 5. Roles & Permissions

Uses existing `roles` table with JSONB permissions.

### Command Access Matrix

| Command | admin | manager | agent | viewer |
|---------|-------|---------|-------|--------|
| /start, /menu | Yes | Yes | Yes | Yes |
| /leads (list) | Yes | Yes | Yes | Yes r/o |
| /lead (details) | Yes | Yes | Yes | Yes r/o |
| /lead_assign | Yes | Yes | self only | No |
| /lead_qualify | Yes | Yes | No | No |
| /lead_convert | Yes | Yes | No | No |
| /lead_close | Yes | Yes | Yes | No |
| /client_create | Yes | Yes | Yes | No |
| /client_update | Yes | Yes | Yes own | No |
| /property_create | Yes | Yes | Yes | No |
| /deal_status | Yes | Yes | No | No |
| /task_create | Yes | Yes | Yes | No |
| /task_assign | Yes | Yes | Yes | No |
| /admin | Yes | No | No | No |

### Permission Enforcement
- AuthMiddleware loads user role on every interaction
- Handler checks permissions before executing
- Unauthorized commands: "У вас нет прав на это действие" + logged to security audit

---

## 6. Main Menu

### Layout

Row 1: [Лиды] [Клиенты]
Row 2: [Объекты] [Сделки]
Row 3: [Задачи] [Отчеты]
Row 4: [Админ] (admin only)

### Implementation
- ReplyKeyboardMarkup, resize_keyboard=True
- Each button routes to module handler via text match
- Main menu sent on /start, /menu, or after completing any action
- InlineKeyboard "Назад" button on every card leads to module list
- Module lists use InlineKeyboard with pagination

---

## 7. Lead Module

### Commands

| Command | Action | Auth |
|---------|--------|------|
| /leads | List paginated leads (new first) | read |
| /lead {id} | View lead card | read |
| /lead_search {text} | Search by name/phone | read |
| /lead_assign {id} | Assign to agent | assign |
| /lead_qualify {id} | Qualify lead | qualified |
| /lead_convert {id} | Convert lead -> client (+ optional deal) | qualified |
| /lead_close {id} {reason} | Close lead (lost/spam) | update |

### Lead List Display

```
Лиды (стр. 1/3)
Всего: 24 | Новых: 7

1. Иванов П. | telegram | qualifying | hot
2. Петров С. | avito | new | warm
3. Telegram Lead | manual | new | cold

[< Назад] [Еще >]
```

- Sorted by created_at DESC
- Priority icons: hot, warm, cold
- 5 per page with pagination

### Lead Card

```
ЛИД #125

Иванов Петр Сергеевич
+7 (912) 345-67-89
ivanov@email.com
Telegram: @ivanov_ps

Источник: telegram
Статус: qualifying
Приоритет: warm
Скоринг: 0.78

Бюджет: 10 000 000 - 15 000 000 руб.
Тип: квартира
Заметки: Хочет 3-комнатную в Приморском районе

Ответственный: Сергей (manager)
Создан: 07.06.2026

[Назначить] [Квалифицировать] [Конвертировать] [Закрыть] [Назад]
```

### Action Flows

**Assign:**
1. Click "Назначить" -> show agent list inline
2. Select agent -> POST /api/v1/leads/{id}/assign?user_id={uid}
3. Response: "Лид #125 назначен на Сергей"

**Qualify:**
1. Click "Квалифицировать"
2. If score < 0.5: confirm dialog
3. POST /api/v1/leads/{id}/qualify -> "Лид квалифицирован"

**Convert:**
1. Click "Конвертировать"
2. Prompt: "Создать сделку?" [Да / Нет]
3. POST /api/v1/leads/{id}/convert -> "Лид конвертирован в клиента #42. Сделка #15 создана."

**Close:**
1. Click "Закрыть" -> choose reason [Lost] [Spam]
2. POST /api/v1/leads/{id}/close -> "Лид #125 закрыт (lost)"

### FSM: Lead Create (handle_new_lead)

Step 1: "Введите имя (или /cancel)" -> Name (required)
Step 2: "Телефон (опционально)" -> Phone
Step 3: "Бюджет (опционально)" -> Budget
Step 4: "Тип недвижимости" -> Property type
Step 5: "Примечание (опционально)" -> Notes
Confirm: "Создать лид?" [Да] [Нет]
Final: POST /api/v1/leads -> "Лид #126 создан"

---

## 8. Client Module

### Commands

| Command | Action |
|---------|--------|
| /clients | List clients (paginated) |
| /client {id} | View client card |
| /client_search {text} | Search by name or phone |

### Client Card

```
КЛИЕНТ #42

Иванов Петр Сергеевич
+7 (912) 345-67-89
ivanov@email.com

Источник: telegram (конвертирован 07.06.2026)
Статус: active

История:
  Объекты: 2
  Сделки: 1 (в работе)
  Задачи: 3 (1 активная)
  Коммуникации: 12

[Объекты] [Сделки] [Задачи] [История] [Редактировать] [Назад]
```

### History Aggregation

GET /api/v1/clients/{id}/history -> client + properties + deals + tasks + communications

Bot renders each section as a separate message or accordion via callback.

---

## 9. Property Module

### Commands

| Command | Action |
|---------|--------|
| /properties | List properties (paginated) |
| /property {id} | View property card |
| /property_search {text} | Search by address or cadastre |

### Property Card

```
ОБЪЕКТ #78

ул. Садовая, 15, кв. 42
Тип: квартира
Цена: 12 500 000 руб.
Площадь: 65 м2
Комнат: 3
Статус: active

Собственник: Иванов П.С.

Документы (2):
  - Выписка ЕГРН (07.06.2026)
  - Договор купли-продажи (01.06.2026)

Связанные сделки (1):
  - Сделка #42 - в работе

[Документы] [Сделки] [Назад]
```

## 10. Deal Module

### Commands

| Command | Action | Auth |
|---------|--------|------|
| /deals | List deals (active first) | read |
| /deal {id} | View deal card | read |
| /deal_status {id} {status} | Change deal status (validated by CRM) | update |

### Deal Card

```
СДЕЛКА #42

Тип: покупка
Статус: offer_made

Объект: ул. Садовая, 15, кв. 42 (12.5M руб.)

Участники:
  - Покупатель: Иванов П.С. (клиент #42)
  - Продавец: Петров А.В. (клиент #45)

Создана: 07.06.2026
Ответственный: Сергей (manager)

[Сменить статус] [Назад]
```

### Status Machine

negotiation -> offer_made -> under_review -> approved -> closed

Any active status -> cancelled

All transitions validated by CRM Service. Bot is thin client.

---

## 11. Task Module

### Commands

| Command | Action |
|---------|--------|
| /tasks | List tasks (active first) |
| /task {id} | View task card |
| /task_create | FSM create task |
| /task_complete {id} | Mark complete |
| /task_reopen {id} | Reopen task |

### FSM: Task Create

Step 1: "Введите название задачи" -> Title (required)
Step 2: "Описание (или /skip)" -> Description
Step 3: "Дата выполнения ДД.ММ.ГГГГ (или /skip)" -> Due date
Step 4: "Выберите исполнителя" -> Select from employee list
Confirm: "Создать задачу?"
  Title: ...
  Description: ...
  Due: 15.06.2026
  Assignee: Сергей
  [Да] [Нет] [Редактировать]

Final: POST /api/v1/tasks -> "Задача #89 создана" + notification to assignee

### Task Card

```
ЗАДАЧА #89

Подготовить договор для Иванова
Подготовить все документы к подписанию
Срок: 15.06.2026
Статус: in_progress
Исполнитель: Сергей (manager)
Приоритет: high

[Завершить] [Переоткрыть] [Назад]
```

---

## 12. Notifications

### Architecture

Background asyncio task polls /api/v1/notifications/pending every 30 seconds.
No webhook support in Sprint 3.

### Template Table

| Event | Template | Priority |
|-------|----------|----------|
| lead.created | Новый лид! {name}, {source}, {budget} | high |
| lead.assigned | Вам назначен лид {name} | high |
| task.created | Новая задача {title} | high |
| task.assigned | Вам назначена задача {title} | high |
| task.overdue | Просрочена задача {title} | medium |
| deal.status_changed | Статус сделки #{id}: {old} -> {new} | medium |

### Polling Implementation

```python
class NotificationPoller:
    async def poll(self):
        while True:
            events = await self.crm.get_pending_events(since=self.last_check)
            for event in events:
                await self.dispatch(event)
            self.last_check = datetime.utcnow()
            await asyncio.sleep(30)
```

### Delivery Rules
- Notifications sent only to assigned user
- Lead notifications: all agents with lead:read permission
- Task overdue: once per day (check last_notified_at)
- InlineKeyboard with "Открыть" button linking to entity card

---

## 13. CRM API Integration

### CRMClient Class

```python
class CRMClient:
    def __init__(self, base_url, api_key, timeout=30.0):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "X-API-Key": api_key,
                "X-Source-Component": "telegram_bot",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    # Leads
    async def get_leads(self, page=1, status=None): ...
    async def get_lead(self, lead_id): ...
    async def create_lead(self, data): ...
    async def assign_lead(self, lead_id, user_id): ...
    async def qualify_lead(self, lead_id, user_id): ...
    async def convert_lead(self, lead_id, user_id, create_deal=False): ...
    async def close_lead(self, lead_id, status): ...

    # Clients
    async def get_clients(self, page=1): ...
    async def get_client(self, client_id): ...
    async def search_clients(self, query): ...
    async def get_client_history(self, client_id): ...

    # Properties
    async def get_properties(self, page=1): ...
    async def get_property(self, property_id): ...
    async def search_properties(self, query): ...

    # Deals
    async def get_deals(self, page=1): ...
    async def get_deal(self, deal_id): ...
    async def change_deal_status(self, deal_id, status): ...

    # Tasks
    async def get_tasks(self, page=1): ...
    async def get_task(self, task_id): ...
    async def create_task(self, data): ...
    async def complete_task(self, task_id, completed_by): ...
    async def reopen_task(self, task_id): ...

    # Auth
    async def get_user_by_telegram_id(self, telegram_id): ...
```

### Error Handling Policy

| HTTP Status | Bot Response |
|-------------|--------------|
| 200-299 | Parse JSON, return DTO |
| 400 | "Проверьте введенные данные: {detail}" |
| 401/403 | "Доступ запрещен. Обратитесь к администратору." |
| 404 | "Не найдено. Возможно, элемент был удален." |
| 409 | "Конфликт: такой элемент уже существует." |
| 422 | Show field errors |
| 429 | "Слишком много запросов. Повторите через минуту." |
| 500 | "Внутренняя ошибка сервера. Попробуйте позже." |
| Timeout | "Сервер не отвечает. Попробуйте позже." |

### Retry Policy
- Retry on: 429, 502, 503, 504, timeout, connection error
- Exponential backoff: 1s, 3s, 10s
- Max retries: 3
- Circuit breaker: deferred to Sprint 5

---

## 14. Audit Integration

### Source Header
Every API call: X-Source-Component: telegram_bot

### Audit Event Types

| Event | Trigger |
|-------|---------|
| telegram_lead_viewed | Lead card opened |
| telegram_lead_created | Lead created via bot |
| telegram_lead_assigned | Lead assigned |
| telegram_lead_qualified | Lead qualified |
| telegram_lead_converted | Lead -> Client |
| telegram_lead_closed | Lead closed (lost/spam) |
| telegram_client_viewed | Client card opened |
| telegram_client_created | Client created |
| telegram_property_viewed | Property card opened |
| telegram_deal_viewed | Deal card opened |
| telegram_deal_status_changed | Deal status changed |
| telegram_task_created | Task created |
| telegram_task_completed | Task completed |
| telegram_task_reopened | Task reopened |
| telegram_auth_success | Successful login |
| telegram_auth_failure | Failed login |
| telegram_unauthorized_access | Blocked command |

---

## 15. Observability

### Metrics

```python
telegram_updates_total = Counter("telegram_updates_total", "Total updates", ["type"])
telegram_commands_total = Counter("telegram_commands_total", "Commands", ["command", "role"])
telegram_callbacks_total = Counter("telegram_callbacks_total", "Callbacks", ["action", "entity"])
telegram_errors_total = Counter("telegram_errors_total", "Errors", ["type", "handler"])
telegram_active_users = Gauge("telegram_active_users", "Active users in last hour")
telegram_api_latency = Histogram("telegram_api_latency_seconds", "API latency", ["endpoint"])
telegram_notifications_sent = Counter("telegram_notifications_sent", "Notifications sent", ["event_type"])
telegram_auth_failures = Counter("telegram_auth_failures", "Auth failures", ["reason"])
```

### Logging (structlog compatible)

```python
logger = structlog.get_logger("integration")
logger.info(
    "lead_assigned",
    source_component="telegram_bot",
    lead_id=str(lead_id),
    assigned_by=str(user_id),
    request_id=ctx.request_id,
)
```

---

## 16. FSM Architecture

### State Diagrams

LeadCreateFSM:
idle -> AWAITING_NAME -> AWAITING_PHONE -> AWAITING_BUDGET -> AWAITING_PROPERTY_TYPE -> AWAITING_NOTES -> CONFIRM -> idle
(cancel at any step returns to main menu)

TaskCreateFSM:
idle -> AWAITING_TITLE -> AWAITING_DESCRIPTION -> AWAITING_DUE_DATE -> AWAITING_ASSIGNEE -> CONFIRM -> idle

### Storage
- Production: aiogram RedisStorage
- Development: MemoryStorage
- Timeout: 10 minutes inactivity -> FSM.reset() with warning

---

## 17. Callback Data Strategy

### Format
entity:action[:id][:extra]

### Constraint
Max 64 bytes per callback_data.

### Registry

| Callback | Max Length |
|----------|-----------|
| lead:list:{page} | 18 |
| lead:view:{uuid} | 46 |
| lead:assign:{uuid} | 48 |
| lead:qualify:{uuid} | 48 |
| lead:convert:{uuid} | 48 |
| lead:close:{uuid} | 44 |
| client:view:{uuid} | 48 |
| client:history:{uuid} | 50 |
| client:prop:{uuid} | 48 |
| client:deals:{uuid} | 46 |
| client:tasks:{uuid} | 46 |
| prop:view:{uuid} | 46 |
| prop:docs:{uuid} | 44 |
| deal:view:{uuid} | 44 |
| deal:status:{uuid} | 48 |
| task:view:{uuid} | 44 |
| task:complete:{uuid} | 48 |
| task:reopen:{uuid} | 44 |
| menu:main | 9 |
| menu:back:{from} | 16 |
| page:next:{m}:{p} | 24 |
| page:prev:{m}:{p} | 24 |
| cancel | 6 |

### Parsing

```python
from dataclasses import dataclass
from uuid import UUID
import re

PATTERN = re.compile(r"^(\w+):(\w+)(?::([^:]+))?(?::([^:]+))?$")

@dataclass
class Callback:
    entity: str
    action: str
    id: str | None
    extra: str | None

def parse_callback(data: str) -> Callback | None:
    m = PATTERN.match(data)
    if not m:
        return None
    return Callback(m.group(1), m.group(2), m.group(3), m.group(4))
```

---

## 18. Security Review

### Threat Assessment

| Threat | Risk | Mitigation |
|--------|------|-----------|
| Role escalation via forged callback | Medium | AuthMiddleware on every update; server validates too |
| Forged callback_data replay | Low | Callbacks are ephemeral; no tokens in data |
| Deleted user accessing bot | Medium | AuthMiddleware checks deleted_at |
| Soft-deleted entity access | Low | CRM API enforces soft-delete filter |
| API key leak | High | Key in env; restricted service scope |
| Audit bypass | Medium | Audit generated by CRM Service, not bot |
| Command injection in search | Low | httpx escapes URL params |
| FSM timeout data leak | Low | FSM data cleared on timeout |
| Telegram interception | Low | MTProto encrypted; no PII in callbacks |

### Hardening Measures
1. AuthMiddleware on every update (not just /start)
2. Role check before every command
3. No user input reflected without sanitization
4. All errors logged with user_id for audit trail
5. Rate limiting: max 30 requests/minute per user
6. Graceful degradation: no stack traces to user

---

## 19. Architecture Compatibility

### Knowledge Agent (ADR-0011)
- Bot shares API layer with Knowledge Agent
- Future: "show recommendations" -> POST /api/v1/knowledge/recommend

### Client-Facing Bot (Future)
- Reuses CRMClient and API layer
- Different auth (phone or temp token)
- Limited module access
- Different audit source

### Multi-Agent System
- Each bot (staff, client, knowledge) is independent aiogram instance
- Shared: CRM API, audit system, metrics infrastructure
- Bot identities distinguished by X-Bot-Id header

---

## 20. Sprint 3 Deliverables

### Phase 1: Foundation (T1-T3)
- aiogram bootstrap (app.py, config.py)
- AuthMiddleware (auth.py)
- Permissions service (permissions.py)
- CRMClient (crm_client.py)

### Phase 2: Lead + Client + Property (T4-T6)
- leads.py handler + keyboards + FSM
- clients.py handler + keyboards
- properties.py handler + keyboards

### Phase 3: Task + Deal + Admin (T7-T9)
- tasks.py handler + keyboards + FSM
- deals.py handler + keyboards
- admin.py handler
- Notifications (notifications.py)

### Phase 4: Integration (T10-T11)
- Audit integration (RequestContextMiddleware)
- Observability metrics
- Error handling

### Phase 5: Quality (T12-T13)
- Unit tests for all handlers
- Integration tests for CRMClient
- Deployment (systemd service, env config)
