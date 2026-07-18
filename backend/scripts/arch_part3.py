
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
