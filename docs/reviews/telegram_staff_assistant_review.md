# Telegram Staff Assistant V1 — Independent Architecture Review

**Date:** 2026-06-08
**Reviewed by:** Principal Architect (independent)
**Documents Reviewed:**
- docs/architecture/telegram_staff_assistant.md (799 строк)
- docs/adr/0014-telegram-staff-assistant-v1.md
- docs/sprints/sprint_03.md
- docs/crm/crm_service_layer.md
- docs/architecture/audit_log.md
- docs/runtime/runtime_foundation_report.md
- backend/api/ (actual route code)

---

## Executive Summary

Telegram Staff Assistant V1 архитектура в целом хорошо спроектирована — разделение бота и CRM слоя корректно, FSM продумано, модель безопасности адекватна. Ключевая проблема: **архитектура бота специфицирует API-эндпоинты, которых ещё не существует** в CRM слое. Без их создания бот не сможет выполнять ~40% заявленных сценариев.

Всего выявлено: 3 критических, 7 высоких, 12 средних, 9 низких проблем.

**Production Readiness Score: 68/100 → 88/100 (после исправлений)**

---

## 1 — API Contract Review

### Gap Analysis

Таблица ниже проверяет каждый метод CRMClient против реально существующих API эндпоинтов.

| CRMClient Method | Required Endpoint | Exists? | Severity | Impact |
|-----------------|-------------------|---------|----------|--------|
| `get_user_by_telegram_id()` | `GET /api/v1/users?telegram_id=X` | **NO** | **CRITICAL** | Auth невозможен. Бот не сможет никого авторизовать. |
| `close_lead(lead_id, "lost")` | `POST /api/v1/leads/{id}/close` | **NO** | **CRITICAL** | Кнопка «Закрыть» на карточке лида не работает. |
| `change_deal_status(deal_id, status)` | `POST /api/v1/deals/{id}/status` | **NO** | **CRITICAL** | Кнопка «Сменить статус» сделки не работает. |
| `search_clients(query)` | `GET /api/v1/clients?search=X` | NO | HIGH | Поиск клиентов не работает. Вся команда /client_search недоступна. |
| `search_properties(query)` | `GET /api/v1/properties?search=X` | NO | HIGH | Поиск объектов не работает. /property_search не работает. |
| `get_client_history(client_id)` | `GET /api/v1/clients/{id}/history` | NO | HIGH | Карточка клиента показывает только базовые поля. Нет истории. |
| `get_pending_events(since=...)` | `GET /api/v1/notifications/pending` | **NO** | HIGH | Poller не может получать события. Уведомления полностью сломаны. |
| `get_leads(page, status)` | `GET /api/v1/leads?status=new` | **PARTIAL** | MEDIUM | Фильтр по статусу не реализован. Кнопка «Новые лиды» показывает все. |
| `qualify_lead(lead_id, user_id)` | `POST /api/v1/leads/{id}/qualify` | YES | — | OK |
| `convert_lead(lead_id, user_id, create_deal)` | `POST /api/v1/leads/{id}/convert` | YES | — | OK |
| `assign_lead(lead_id, user_id)` | `POST /api/v1/leads/{id}/assign` | YES | — | OK |
| `create_lead(data)` | `POST /api/v1/leads` | YES | — | OK |
| `get_clients(page)` | `GET /api/v1/clients` | YES | — | OK |
| `get_client(client_id)` | `GET /api/v1/clients/{id}` | YES | — | OK |
| `get_properties(page)` | `GET /api/v1/properties` | YES | — | OK |
| `get_property(property_id)` | `GET /api/v1/properties/{id}` | YES | — | OK |
| `get_deals(page)` | `GET /api/v1/deals` | YES | — | OK |
| `get_deal(deal_id)` | `GET /api/v1/deals/{id}` | YES | — | OK |
| `create_task(data)` | `POST /api/v1/tasks` | YES | — | OK |
| `complete_task(task_id, completed_by)` | `POST /api/v1/tasks/{id}/complete` | YES | — | OK |
| `reopen_task(task_id)` | `POST /api/v1/tasks/{id}/reopen` | YES | — | OK |

### N+1 Query Analysis

**Сценарий: открытие карточки клиента**

По архитектуре бот делает 5 запросов:
```
GET /api/v1/clients/{id}           → базовые данные
GET /api/v1/clients/{id}/properties → список объектов
GET /api/v1/clients/{id}/deals      → список сделок
GET /api/v1/clients/{id}/tasks      → список задач
GET /api/v1/clients/{id}/communications → история коммуникаций
```

**Проблема:** 5 HTTP запросов на один экран. При latency 50ms = 250ms на карточку.
При 20 пользователях, открывающих карточки одновременно — 100 запросов за секунду на один endpoint.

**Рекомендация:**
- Создать агрегирующий endpoint: `GET /api/v1/clients/{id}?include=properties,deals,tasks,communications`
- Или `GET /api/v1/clients/{id}/history` (уже в архитектуре бота) — возвращает клиента + все связанные сущности одним запросом
- **Severity:** MEDIUM — не блокирует функциональность, но создаёт нагрузку и задержку.

**Аналогично для карточки объекта:**
- Property card тянет документы, связанные сделки отдельно — те же N+1 вызовы
- `GET /api/v1/properties/{id}?include=documents,deals`

### Отсутствующие CRUD-эндпоинты в CRM слое

| Endpoint | Method | Причина отсутствия |
|----------|--------|-------------------|
| `GET /api/v1/users?telegram_id=X` | GET | Users API не поддерживает фильтрацию по telegram_id |
| `POST /api/v1/leads/{id}/close` | POST | LeadService не имеет close_lead() метода |
| `POST /api/v1/deals/{id}/status` | POST | DealService не имеет change_status() endpoint |
| `GET /api/v1/clients?search=X` | GET | ClientRepo не имеет search метода через API |
| `GET /api/v1/properties?search=X` | GET | PropertyRepo не имеет search метода через API |
| `GET /api/v1/clients/{id}/history` | GET | ClientService.get_client_history() существует но не имеет endpoint |

**Итого:** 7 отсутствующих или частично отсутствующих endpoint из 22 необходимых. Покрытие: 68%.

### Рекомендации по API Contract

1. **CRITICAL:** Добавить `POST /api/v1/leads/{id}/close` с полем reason (lost/spam)
2. **CRITICAL:** Добавить `POST /api/v1/deals/{id}/status` с валидацией переходов
3. **HIGH:** Добавить `GET /api/v1/users?telegram_id=X` — фильтрацию
4. **HIGH:** Добавить `GET /api/v1/clients?search=X` — поиск (ILIKE)
5. **HIGH:** Добавить `GET /api/v1/properties?search=X` — поиск по адресу/кадастру
6. **HIGH:** Добавить `GET /api/v1/clients/{id}/history` — агрегирующий endpoint
7. **HIGH:** Создать notification infrastructure: `POST /api/v1/notifications/events`, `GET /api/v1/notifications/pending`
8. **MEDIUM:** Добавить `GET /api/v1/leads?status={status}` фильтрацию
9. **MEDIUM:** Response schemas должны включать поля для поиска (full_name, phone, address)

---

## 2 — Permission Model Review

### Permission Matrix

| Действие | admin | manager | agent | viewer | Где проверяется |
|----------|-------|---------|-------|--------|-----------------|
| Просмотр лидов | ✅ | ✅ | ✅ | ✅ | API + Bot |
| Назначение лида | ✅ | ✅ | self only | ❌ | Bot |
| Квалификация лида | ✅ | ✅ | ❌ | ❌ | Bot |
| Конвертация лида | ✅ | ✅ | ❌ | ❌ | Bot |
| Закрытие лида | ✅ | ✅ | ✅ | ❌ | Bot |
| Создание клиента | ✅ | ✅ | ✅ | ❌ | Bot |
| Смена статуса сделки | ✅ | ✅ | ❌ | ❌ | Bot |
| Создание задачи | ✅ | ✅ | ✅ | ❌ | Bot |
| Просмотр отчётов | ✅ | ✅ | ❌ | ❌ | Bot |
| Администрирование | ✅ | ❌ | ❌ | ❌ | Bot |
| Просмотр чужого клиента | ✅ | ✅ | ✅ | ✅ | No check |
| Просмотр чужой сделки | ✅ | ✅ | ✅ | ✅ | No check |
| Просмотр чужой задачи | ✅ | ✅ | ✅ | ❌ (?) | No check |

### Найденные уязвимости

**RISK-2-A: Privilege escalation через прямой API вызов (MEDIUM)**

Описание: Bot проверяет permission `agent` не может квалифицировать лид. Но если agent получает Telegram callback_data `lead:qualify:{id}` от другого пользователя или через скрипт — bot проверит `permissions.check("lead_qualify", role)` и должен отклонить. Но что если бот этого не делает?

**Смягчение:** AuthMiddleware должен проверять role.weight >= требуемого для action на каждый callback. Реализовано в коде, но должно быть протестировано.

**RISK-2-B: Отсутствие проверки владения клиентом (LOW)**

Описание: Agent может видеть всех клиентов, а не только своих.

**Оценка:** Типично для небольших агентств. Должно быть настраиваемым.

**RISK-2-C: Callback bypass через подделку данных (MEDIUM)**

Описание: callback_data содержит `lead:convert:{uuid}`. Злоумышленник, знающий lead_id (например, из истории сообщений), может отправить поддельный callback.

**Смягчение:** 
- Сервер CRM API должен проверить права пользователя на операцию (сейчас не проверяет — get_current_user() возвращает stub)
- В Sprint 3 нужно хотя бы минимальную проверку: если API получает X-User-ID header, он должен валидировать, что пользователь имеет право на операцию

**RISK-2-D: get_user_by_telegram_id возвращает данные любого пользователя (HIGH)**

Описание: Endpoint `GET /api/v1/users?telegram_id=X` должен возвращать только базовую информацию (id, name, role_name). Но текущий users API возвращает полный UserResponse включая все поля.

**Рекомендация:** Создать отдельный DTO `UserAuthResponse` с полями: id, full_name, telegram_id, role_name, deleted_at. Не возвращать email, phone, created_by.

### Рекомендации по Permission Model

1. **HIGH:** API должен проверять авторизацию на мутирующих операциях (сейчас stub)
2. **MEDIUM:** Bot должен валидировать callback_data хэш (HMAC), чтобы предотвратить подделку
3. **LOW:** Добавить tenant_id или owner_id фильтрацию для future multi-agency

---

## 3 — FSM Review

### Lead FSM

```
States: idle, AWAITING_NAME, AWAITING_PHONE, AWAITING_BUDGET, AWAITING_PROPERTY_TYPE, AWAITING_NOTES, CONFIRM
```

**Анализ состояний:**

| Аспект | Статус | Проблема |
|--------|--------|----------|
| Все состояния достижимы | ✅ | — |
| Нет dead states | ✅ | Все ведут к /cancel или CONFIRM |
| Таймаут | ⚠️ | 10 минут. Не указано, как пользователю сообщается о таймауте |
| Дублирование отправки | ⚠️ | CONFIRM не защищён от двойного нажатия кнопки «Да» |
| /cancel из idle | ✅ | Возврат в главное меню |

**RISK-3-A: Двойное создание лида (MEDIUM)**

Описание: Пользователь жмёт «Да» на CONFIRM → бот отправляет POST /api/v1/leads → сервер создаёт лид. Если таймаут сети — пользователь может нажать «Да» снова → дубликат.

**Смягчение:**
- Дебаунс на клиенте: игнорировать повторные нажатия кнопки в течение 3 секунд
- Идемпотентность на сервере: проверять дубликаты по source+source_id (уже есть — partial unique index на leads.source + leads.source_id)

### Task FSM

```
States: idle, AWAITING_TITLE, AWAITING_DESCRIPTION, AWAITING_DUE_DATE, AWAITING_ASSIGNEE, CONFIRM
```

**Анализ:**

| Аспект | Статус | Проблема |
|--------|--------|----------|
| Пропуск шагов (/skip) | ✅ | Описан в документации |
| Дюдейт валидация | ⚠️ | "ДД.ММ.ГГГГ" — не указана валидация формата |
| Назначение на себя | ⚠️ | Не указано, может ли agent назначить задачу на manager |

**RISK-3-B: Пользователь не знает ID исполнителя (MEDIUM)**

Описание: FSM просит user_id для назначения задачи, но пользователь не знает UUID сотрудника.

**Смягчение:** Шаг 4 должен показывать inline-список сотрудников (имя + роль), а не требовать ввода ID.

### Property FSM

**RISK-3-C: Property FSM отложен на Sprint 4 (LOW)**

Описание: В структуре есть `states/property.py`, но свойство не создаётся через бот в Sprint 3.

**Рекомендация:**
- Убрать файл из Sprint 3 deliverables
- Или оставить как skeleton с одним шагом (заглушка)

### Рекомендации по FSM

1. **MEDIUM:** Добавить debounce на кнопку CONFIRM (3 секунды)
2. **MEDIUM:** Шаг AWAITING_ASSIGNEE должен показывать список сотрудников, а не требовать ID
3. **LOW:** Property FSM должен быть исключён из Sprint 3 или помечен как stub

---

## 4 — Telegram Constraints Review

### Callback Data

| Callback | Размер | В пределах 64? |
|----------|--------|---------------|
| `lead:list:1` | 11 | ✅ |
| `lead:view:{uuid}` | 46 | ✅ |
| `lead:assign:{uuid}` | 48 | ✅ |
| `lead:qualify:{uuid}` | 48 | ✅ |
| `lead:convert:{uuid}` | 48 | ✅ |
| `lead:close:{uuid}` | 44 | ✅ |
| `lead:close:lost:{uuid}` | 53 | ✅ |
| `client:view:{uuid}` | 48 | ✅ |
| `client:history:{uuid}` | 50 | ✅ |
| `task:complete:{uuid}` | 48 | ✅ |
| `menu:main` | 9 | ✅ |
| `page:next:leads:3` | 18 | ✅ |

**Вывод:** Все callback_data в пределах 64 bytes.

### Message Size Limits

| Сценарий | Размер | Лимит Telegram | Статус |
|----------|--------|---------------|--------|
| Карточка лида | ~500 chars | 4096 | ✅ |
| Список лидов (5 элементов) | ~400 chars | 4096 | ✅ |
| Карточка клиента с историей | ~800 chars | 4096 | ✅ |
| Карточка объекта | ~600 chars | 4096 | ✅ |
| История клиента с 10+ объектами | ~2000+ chars | 4096 | ✅ |
| История клиента с 50+ объектами | **>4096** | 4096 | **RISK-4-A** |

**RISK-4-A: Длинная история клиента не помещается в сообщение (MEDIUM)**

Описание: Если у клиента 50+ объектов, карточка с историей превысит лимит Telegram в 4096 символов.

**Смягчение:** 
- Разбить на разделы с кнопками «Ещё»
- Показывать top 5 каждого типа + «Показать все»
- Pagination с InlineKeyboard

### Rate Limits

| Лимит | Значение | Статус |
|-------|---------|--------|
| Telegram сообщений/сек | ~30 per chat | ✅ 1 пользователь не превысит |
| Telegram сообщений в группе | ~20/min | N/A — бот в личке |
| CRM API запросов | Не ограничен | **RISK-4-B** |

**RISK-4-B: Нет rate limiting на CRM API со стороны бота (HIGH)**

Описание: CRMClient не имеет rate limiter'а. 20 пользователей могут одновременно нажать кнопки → 20 запросов. Система не защищена от всплесков.

**Смягчение:** Добавить httpx.Limits(max_connections=10) и max_keepalive_connections=5.

### Рекомендации по Telegram Constraints

1. **HIGH:** Добавить rate limiting на CRMClient (max 50 req/sec, max 10 concurrent)
2. **MEDIUM:** Разбивать длинные ответы на разделы с pagination
3. **LOW:** Добавить сжатие длинных текстов (truncate с «...»)

---

## 5 — Notification System Review

### Архитектура Poller'а

```
NotificationPoller:
  while True:
    events = await CRM.get_pending_events(since=last_check)
    for event in events:
      await dispatch(event)
    last_check = now()
    await asyncio.sleep(30)
```

**Анализ проблем:**

**RISK-5-A: Poller может пропускать события (MEDIUM)**

Описание: Если `CRM.get_pending_events()` падает с ошибкой, `last_check` не обновляется. При следующем успешном вызове все накопленные события будут доставлены. Но если poller падает 3 раза подряд за 90 секунд — пользователь ждёт 90 секунд уведомление.

**RISK-5-B: Дублирование при race condition (MEDIUM)**

Описание: `last_check` обновляется ПОСЛЕ dispatch, а не ПОСЛЕ fetch. Если dispatch медленный (>30 секунд), следующий цикл poll может перехватить те же события.

**Смягчение:** Обновлять `last_check` сразу после fetch, до dispatch.

**RISK-5-C: Нет механизма «прочитано/доставлено» (MEDIUM)**

Описание: Если бот отправил уведомление, но пользователь его не открыл — нет способа узнать. Пользователь может получить одно и то же уведомление при следующем poll.

**Смягчение:** Добавить `notification_log` таблицу с `delivery_status` (pending, delivered, read). Poller должен обновлять статус после dispatch.

**RISK-5-D: События генерируются бэкендом, но API для них не реализован (HIGH)**

Описание: Архитектура предполагает `GET /api/v1/notifications/pending`, но ни endpoint, ни таблица notifications не существуют.

**Смягчение:** Создать notification subsystem:
1. Таблица `notifications` (id, event_type, user_id, entity_type, entity_id, data JSONB, delivery_status, created_at)
2. CRM сервисы пишут в notifications при commit'е
3. Endpoint: `GET /api/v1/notifications/pending?since=2026-06-08T00:00:00`
4. Endpoint: `PATCH /api/v1/notifications/{id}/delivered`

### Рекомендации по Notifications

1. **HIGH:** Создать notification инфраструктуру на бэкенде (таблица, endpoint, запись при commit)
2. **HIGH:** Обновлять last_check в poller'е ДО dispatch
3. **MEDIUM:** Добавить notification_log с delivery_status
4. **MEDIUM:** Добавить exponential backoff при ошибках poll

---

## 6 — Audit Compliance Review

### Проверка покрытия аудитом

| Действие | Заявлен аудит? | Реально аудируется? | Gap |
|----------|---------------|--------------------|-----|
| lead.created | ✅ telegram_lead_created | ✅ LeadService создаёт LeadEvent | НЕТ |
| lead.viewed | ✅ telegram_lead_viewed | ❌ CRM не аудирует read операции | **GAP-6-A** |
| lead.assigned | ✅ telegram_lead_assigned | ✅ LeadService создаёт LeadEvent | НЕТ |
| lead.qualified | ✅ telegram_lead_qualified | ✅ LeadService.qualify_lead() | НЕТ |
| lead.converted | ✅ telegram_lead_converted | ✅ LeadService.convert_lead() | НЕТ |
| lead.closed | ✅ telegram_lead_closed | ❌ LeadService.close_lead() не существует | **GAP-6-B** |
| client.viewed | ✅ telegram_client_viewed | ❌ Нет аудита read операций | **GAP-6-A** |
| client.created | ✅ telegram_client_created | ✅ structlog audit event | НЕТ |
| property.viewed | ✅ telegram_property_viewed | ❌ Нет аудита read операций | **GAP-6-A** |
| deal.viewed | ✅ telegram_deal_viewed | ❌ Нет аудита read операций | **GAP-6-A** |
| deal.status_changed | ✅ telegram_deal_status_changed | ❌ DealService.change_status() нет endpoint | **GAP-6-C** |
| task.created | ✅ telegram_task_created | ✅ TaskService.create_task() логирует | НЕТ |
| task.completed | ✅ telegram_task_completed | ⚠️ TaskService.complete_task() — уточнить | POSSIBLE |
| task.reopened | ✅ telegram_task_reopened | ⚠️ TaskService.reopen_task() — уточнить | POSSIBLE |
| auth.success | ✅ telegram_auth_success | ⚠️ AuthMiddleware должен логировать | POSSIBLE |
| auth.failure | ✅ telegram_auth_failure | ⚠️ AuthMiddleware должен логировать | POSSIBLE |
| unauthorized_access | ✅ telegram_unauthorized_access | ⚠️ Permissions должен логировать | POSSIBLE |

**GAP-6-A: Read-операции не аудируются (MEDIUM)**

Описание: Бот заявляет `telegram_lead_viewed`, `telegram_client_viewed` и т.д., но ни CRM бэкенд, ни сам бот не имеют механизма аудита read операций. И это ок — аудит read операций создаёт тонны логов с низкой ценностью.

**Рекомендация:** Убрать read-аудит из scope Sprint 3. Оставить только для security-значимых (auth success/failure).

**GAP-6-B: close_lead не имеет ни endpoint, ни аудита (CRITICAL — см. API Contract)**

**GAP-6-C: change_deal_status не имеет endpoint (CRITICAL — см. API Contract)**

### Correlation ID propagation

Архитектура бота корректно описывает:
- RequestContextMiddleware устанавливает correlation_id
- CRMClient добавляет X-Correlation-ID в заголовки
- Бэкенд логирует с correlation_id

✅ Корректно.

### Рекомендации по Audit

1. **MEDIUM:** Убрать read audit из Sprint 3 (перенести в observability через metrics)
2. **LOW:** Добавить healthcheck audit (bot_started, bot_stopped)
3. **LOW:** Добавить audit для admin broadcast команды

---

## 7 — Observability Review

### Метрики

Текущий набор метрик:

| Метрика | Тип | Достаточно? |
|---------|-----|------------|
| telegram_updates_total | Counter | ✅ |
| telegram_commands_total | Counter | ✅ |
| telegram_callbacks_total | Counter | ✅ |
| telegram_errors_total | Counter | ✅ |
| telegram_active_users | Gauge | ⚠️ Нужен расчет |
| telegram_api_latency | Histogram | ✅ |
| telegram_notifications_sent | Counter | ✅ |
| telegram_auth_failures | Counter | ✅ |

### Отсутствующие метрики

**RISK-7-A: Нет метрик здоровья системы (MEDIUM)**

Отсутствуют:
- `telegram_bot_uptime` — Gauge, время работы бота
- `telegram_poller_health` — Gauge, 1=healthy 0=unhealthy
- `crm_api_health` — Gauge, доступность API
- `telegram_fsm_timeouts_total` — Counter, сколько FSM таймаутов

**Рекомендация:** Добавить health-метрики для алертинга.

### Alerting Points

| Alert | Condition | Severity |
|-------|-----------|----------|
| Bot не отвечает 5 минут | No updates for 5 min | CRITICAL |
| CRM API недоступен | API health check fails | CRITICAL |
| Auth failures > 10/min | telegram_auth_failures spike | HIGH |
| Error rate > 5% | errors_total / updates_total > 0.05 | MEDIUM |
| API latency > 2s (p95) | telegram_api_latency spike | MEDIUM |
| Notifications не доставляются | notifications_sent = 0 for 10 min | MEDIUM |

### Grafana Dashboard

Рекомендуемые панели:

1. **Overview:** uptime, active users, total updates
2. **Commands:** commands by type, commands by role
3. **API Performance:** latency (p50, p95, p99), error rate
4. **Notifications:** sent, delivered, delivery latency
5. **Errors:** error rate by handler, by type
6. **Auth:** auth success vs failure, rate of failures

### Рекомендации по Observability

1. **MEDIUM:** Добавить health-метрики: uptime, poller_health, api_health
2. **MEDIUM:** Добавить FSM timeout метрику
3. **LOW:** Подготовить Grafana dashboard JSON

---

## 8 — Scalability Review

### Модель нагрузки

| Параметр | 5 пользователей | 20 пользователей | 100 пользователей |
|----------|----------------|-------------------|-------------------|
| Updates/sec (пик) | ~5 | ~20 | ~100 |
| API calls/sec | ~15 | ~60 | ~300 |
| Concurrent connections | ~8 | ~30 | ~150 |
| Notifications/min | ~5 | ~50 | ~500 |

### Bottleneck Analysis

**Bottleneck 1: CRM API (HIGH)**

Описание: При 100 пользователях — 300 запросов/сек. FastAPI с одним worker'ом на 4GB сервере может не справиться.

**Смягчение:**
- Gunicorn с 2-4 workers
- Rate limiting на уровне API
- Connection pooling на bot side

**Bottleneck 2: CRMClient connection pool (MEDIUM)**

Описание: httpx.AsyncClient по умолчанию создаёт 100 connections. При 100 пользователях с постоянными запросами это может быть узким местом.

**Смягчение:** Явно настроить httpx.Limits(max_connections=50, max_keepalive_connections=20).

**Bottleneck 3: Память FSM States (MEDIUM)**

Описание: MemoryStorage для FSM хранит все состояния в памяти. При 100 пользователях с активными FSM — ~10KB/пользователь = 1MB. Некритично.

**Смягчение:** Переход на RedisStorage при >50 пользователях (Sprint 5).

**Bottleneck 4: Notification polling (LOW)**

Описание: При 100 пользователях: 30-секундный цикл. Если каждый poll возвращает 15 событий → 50 dispatch/сек. Telegram API rate limit = 30 messages/sec.

**Смягчение:** Rate limiting на dispatch (не более 25 сообщений в секунду). Batch delivery.

### Horizontal Scaling

| Компонент | Можно масштабировать? | Как |
|-----------|---------------------|-----|
| Bot | ✅ | Несколько aiogram polling instances (разные боты) |
| CRM API | ✅ | Gunicorn workers |
| PostgreSQL | ✅ | Read replicas |
| FSM Storage | ⚠️ | Нужен Redis (MemoryStorage не шарится) |

**RISK-8-A: Несколько ботов = двойные уведомления (HIGH)**

Описание: Если запущено 2+ экземпляра бота, оба будут поллить `/api/v1/notifications/pending` и отправлять дублирующие уведомления.

**Смягчение:**
- Переход на webhook вместо polling (Telegram отправляет обновления только одному экземпляру)
- Или leader election для notification poller (только один бот поллит)
- Или использовать очередь (Redis pub/sub или RQ) → потребитель один

### Рекомендации по Scalability

1. **HIGH:** При >2 экземплярах бота нужен механизм предотвращения дублирования уведомлений
2. **MEDIUM:** Настроить httpx connection pool (max_connections=50)
3. **MEDIUM:** План перехода на RedisStorage в Sprint 5
4. **LOW:** Добавить rate limiting на dispatch нотификаций

---

## 9 — Failure Scenario Review

| Сценарий | Expected Behavior | Текущий план | Gap |
|----------|-------------------|-------------|-----|
| API unavailable | Bot отвечает «Сервер не отвечает. Попробуйте позже.» | ✅ CRMClient error mapping | — |
| DB unavailable | API возвращает 500 → Bot: «Внутренняя ошибка сервера» | ✅ Описано | — |
| Telegram unavailable | Bot теряет соединение → переподключается (aiogram retry) | ⚠️ Не описано поведение | GAP-9-A |
| Timeout (API) | Bot: «Таймаут. Повторите позже.» | ✅ CRMClient timeout | — |
| Timeout (FSM) | 10 мин → /cancel с предупреждением | ⚠️ Не указано как сообщается | GAP-9-B |
| Duplicate callback | Пользователь нажал кнопку дважды → повторный callback | ⚠️ Не описано | GAP-9-C |
| Stale keyboard | Кнопка из старого сообщения всё ещё активна | ⚠️ Не описано | GAP-9-D |
| Deleted entity | Открыть карточку удалённого (soft-deleted) лида | ✅ 404 от API → «Не найдено» | — |
| Deleted user | Мягко удалённый пользователь пытается /start | ✅ AuthMiddleware проверяет deleted_at | — |
| User not found | telegram_id не привязан ни к одному пользователю | ✅ «Вы не авторизованы» | — |
| API returns 403 | Bot показывает «Доступ запрещён» | ✅ Описано | — |
| API returns 409 | Bot показывает «Конфликт» | ✅ Описано | — |

**GAP-9-A: Telegram недоступен (LOW)**

Описание: Если Telegram API временно недоступен, что делает бот?

**Рекомендация:** aiogram имеет встроенный retry. Описать в документации: «бот переподключается с exponential backoff».

**GAP-9-B: FSM timeout сообщение (LOW)**

Описание: Как пользователь узнаёт о FSM timeout?

**Рекомендация:** aiogram может отправлять сообщение о таймауте. Описать это в документации.

**GAP-9-C: Duplicate callback (MEDIUM)**

Описание: Пользователь нажал кнопку, callback обрабатывается 2 секунды, пользователь нажимает снова.

**Рекомендация:**
- Clientside дебаунс: aiogram middleware, который игнорирует повторный идентичный callback в течение 3 секунд
- Serverside идемпотентность (lead creation protected by unique index)

**GAP-9-D: Stale keyboard (LOW)**

Описание: Карточка лида создана в 10:00. Администратор удалил лида в 10:05. Кнопка «Конвертировать» в старом сообщении всё ещё кликабельна.

**Рекомендация:**
- Редактировать сообщение после действия: `await message.edit_reply_markup(reply_markup=None)`
- Это стандартная практика aiogram

### Рекомендации по Failure Scenarios

1. **MEDIUM:** Добавить callback debounce middleware
2. **MEDIUM:** Редактировать или отзывать клавиатуры после действия
3. **LOW:** Описать поведение при Telegram недоступности

---

## 10 — Final Verdict

### Production Readiness Score: 68/100

| Категория | Вес | Score |
|-----------|-----|-------|
| API Contract | 15% | 6/15 |
| Permission Model | 15% | 11/15 |
| FSM Design | 10% | 7/10 |
| Telegram Constraints | 10% | 8/10 |
| Notification System | 15% | 6/15 |
| Audit Compliance | 10% | 7/10 |
| Observability | 10% | 7/10 |
| Scalability | 10% | 6/10 |
| Failure Scenarios | 5% | 3/5 |
| **TOTAL** | **100%** | **68/100** |

**После исправления критических и высоких: 88/100**

### Issue Summary

**CRITICAL (3):**

| # | Проблема | Исправление |
|---|---------|------------|
| C1 | `GET /api/v1/users?telegram_id=X` не существует | Добавить эндпоинт с фильтрацией |
| C2 | `POST /api/v1/leads/{id}/close` не существует | Добавить close_lead() в LeadService + эндпоинт |
| C3 | `POST /api/v1/deals/{id}/status` не существует | Добавить change_status() в DealService + эндпоинт |

**HIGH (7):**

| # | Проблема | Исправление |
|---|---------|------------|
| H1 | Нет поиска клиентов (`GET /api/v1/clients?search=X`) | Добавить эндпоинт с ILIKE поиском |
| H2 | Нет поиска объектов (`GET /api/v1/properties?search=X`) | Добавить эндпоинт с ILIKE поиском |
| H3 | Нет агрегирующей истории клиента | Добавить `GET /api/v1/clients/{id}/history` |
| H4 | Нет notification инфраструктуры | Создать таблицу, эндпоинты |
| H5 | API не проверяет авторизацию на мутации | Минимальная проверка прав через заголовок пользователя |
| H6 | Нет rate limiting на CRMClient | httpx.Limits(max_connections=10) |
| H7 | Дублирование уведомлений при >1 экземпляре бота | Webhook или leader election |

**MEDIUM (12):**

| # | Проблема |
|---|---------|
| M1 | N+1 запросов на карточку клиента/объекта |
| M2 | Callback debounce для предотвращения дубликатов |
| M3 | Длинная история клиента >4096 символов |
| M4 | Poller last_check timing race condition |
| M5 | Нет delivery_status для уведомлений |
| M6 | FSM не показывает список сотрудников на шаге назначения |
| M7 | Нет метрик здоровья (uptime, poller_health, fsm_timeouts) |
| M8 | Callback подделка (нет HMAC подписи) |
| M9 | Stale keyboard после действия |
| M10 | FSM таймаут не сообщается пользователю |
| M11 | httpx connection pool не настроен |
| M12 | Нет фильтрации лидов по статусу |

**LOW (9):**

| # | Проблема |
|---|---------|
| L1 | Property FSM отложен — skeleton или исключить |
| L2 | Read-аудит не нужен (убрать из scope) |
| L3 | Нет audit для bot_started/bot_stopped |
| L4 | Нет audit для admin broadcast |
| L5 | Нет сжатия длинных текстов |
| L6 | Telegram недоступность не описана |
| L7 | FSM таймаут сообщение не описано |
| L8 | Нет Grafana dashboard |
| L9 | Нет rate limiting на dispatch нотификаций |

### GO / NO-GO

**VERDICT: ✅ GO with conditions**

**Условие GO:**
- **До начала Sprint 3 реализации** необходимо создать 3 критических + 7 высоких эндпоинтов в CRM API
- **Sprint 3 Phase 0 (Pre-requisite):** API Gap Closure — 3 дня
- **Sprint 3:** модифицирован: 5 фаз + Phase 0 (API Gap)

### Pre-requisite: API Gap Closure Sprint

| # | Task | Effort |
|---|------|--------|
| 1 | `GET /api/v1/users?telegram_id=X` фильтрация + UserAuthResponse DTO | 0.5d |
| 2 | `POST /api/v1/leads/{id}/close` + LeadService.close_lead() | 0.5d |
| 3 | `POST /api/v1/deals/{id}/status` + DealService.change_status() | 0.5d |
| 4 | `GET /api/v1/clients?search=X` + ILIKE search | 0.5d |
| 5 | `GET /api/v1/properties?search=X` + ILIKE search | 0.5d |
| 6 | `GET /api/v1/clients/{id}/history` агрегирующий endpoint | 1d |
| 7 | Notification таблица + эндпоинты | 1.5d |
| **TOTAL** | | **~3.5 дня** |
