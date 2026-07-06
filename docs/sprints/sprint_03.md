# Sprint 3 — Telegram Staff Assistant V1

**Date:** 2026-06-07
**Duration:** ~2 weeks
**Pre-requisites:** Sprint 1 (Infrastructure), Sprint 1B (Runtime), Sprint 2 (CRM Service Layer)
**Architecture Doc:** docs/architecture/telegram_staff_assistant.md
**ADR:** ADR-0014

---

## Overview

Implement the first production UI for Real Estate OS — a Telegram bot for staff CRM operations.

### Architecture Principle

```
Telegram -> aiogram -> CRMClient (httpx) -> FastAPI -> CRM Service -> Repository -> PostgreSQL
NO direct DB access
NO business logic in bot
NO SQLAlchemy in bot
```

---

## Phase 1: Foundation (T1-T3)

### T1: aiogram Bootstrap

**Files:**
- bot/app.py — create_dispatcher(), register_middleware(), main()
- bot/config.py — BOT_TOKEN, API_BASE_URL, ADMIN_IDS, LOG_LEVEL from env

**Tasks:**
1. Create bot/ directory structure
2. Add aiogram + httpx + structlog to requirements.txt
3. Create app.py with dispatcher factory
4. Create config.py with env validation (pydantic-settings)
5. Verify bot starts and responds to /start

**Acceptance:** Bot starts, /start returns message (auth or unauthorized)

---

### T2: Auth Middleware

**Files:**
- bot/middleware/__init__.py
- bot/middleware/auth.py — AuthMiddleware class

**Tasks:**
1. Capture message.from_user.id on every update
2. Check telegram_id via CRMClient.get_user_by_telegram_id()
3. Cache successful auth for 1 hour
4. Reject unauthorized users with "Вы не авторизованы"
5. Handle: deleted user, soft-deleted user, role changes

**Acceptance:** Only users with valid telegram_id in users table can interact with bot

---

### T3: Permissions Service

**Files:**
- bot/services/__init__.py
- bot/services/permissions.py — PermissionService

**Tasks:**
1. Define role hierarchy: admin (100) > manager (50) > agent (30) > viewer (10)
2. Command -> minimum weight mapping
3. check_permission(user, command) -> bool
4. Used by handlers to gate commands

**Acceptance:** Handlers can call permissions.check(cmd, role) to authorize

---

## Phase 2: Lead + Client + Property (T4-T6)

### T4: Lead Module

**Files:**
- bot/handlers/__init__.py
- bot/handlers/leads.py
- bot/keyboards/leads.py
- bot/states/lead.py

**Tasks:**
1. /leads — list paginated leads (new first)
2. /lead {id} — view lead card with all fields
3. /lead_search {text} — search by name/phone
4. /lead_assign {id} [user_id] — assign to agent
5. /lead_qualify {id} — qualify lead
6. /lead_convert {id} [--deal] — convert to client
7. /lead_close {id} {reason} — close (lost/spam)
8. FSM: handle_new_lead — 5-step wizard (name, phone, budget, type, notes)
9. InlineKeyboard: assign, qualify, convert, close buttons
10. Pagination InlineKeyboard: next/prev pages

**LeadEvent integration:** Every mutation creates LeadEvent via CRM API.

**Acceptance:** Full lead lifecycle from creation to conversion, all via Telegram

---

### T5: Client Module

**Files:**
- bot/handlers/clients.py
- bot/keyboards/clients.py

**Tasks:**
1. /clients — list paginated clients
2. /client {id} — view client card
3. /client_search {text} — search by name/phone
4. Client card sections: contacts, properties, deals, tasks, history
5. InlineKeyboard for each section

**Acceptance:** View client card with aggregated history

---

### T6: Property Module

**Files:**
- bot/handlers/properties.py
- bot/keyboards/properties.py
- bot/states/property.py

**Tasks:**
1. /properties — list paginated
2. /property {id} — view property card
3. /property_search {text} — search by address/cadastre
4. Property card: address, price, status, owner, documents, linked deals
5. FSM: handle_new_property (future — Sprint 4)

**Acceptance:** Search and view property cards

---

## Phase 3: Task + Deal + Admin (T7-T9)

### T7: Task Module

**Files:**
- bot/handlers/tasks.py
- bot/keyboards/tasks.py
- bot/states/task.py

**Tasks:**
1. /tasks — list active tasks
2. /task {id} — view task card
3. /task_create — FSM wizard (title, description, due_date, assignee)
4. /task_complete {id} — mark complete with completed_by
5. /task_reopen {id} — reopen task
6. InlineKeyboard for complete/reopen actions
7. FSM cancellation via /cancel

**Acceptance:** Full task lifecycle via Telegram FSM

---

### T8: Deal Module

**Files:**
- bot/handlers/deals.py
- bot/keyboards/deals.py

**Tasks:**
1. /deals — list active deals
2. /deal {id} — view deal card
3. /deal_status {id} {status} — change status (validated by CRM)
4. Card: type, status, property, participants, history

**Acceptance:** View and update deal status

---

### T9: Notifications + Admin

**Files:**
- bot/services/notifications.py
- bot/handlers/admin.py

**Tasks:**
1. Background poller: GET /api/v1/notifications/pending every 30s
2. Notification templates for: lead.created, lead.assigned, task.created, task.assigned, task.overdue, deal.status_changed
3. Delivery: direct send_message to user
4. /admin: user list, broadcast (admin only)

**Acceptance:** Assigned users receive notifications within 30s

---

## Phase 4: Integration (T10-T11)

### T10: Audit Integration

**Files:**
- bot/middleware/request_context.py

**Tasks:**
1. RequestContextMiddleware: inject user_id, request_id, correlation_id
2. All handlers pass context to CRM API headers
3. All actions logged with source_component=telegram_bot
4. Audit events for: auth_success, auth_failure, unauthorized_access

**Acceptance:** Every bot action traces to CRM audit log

---

### T11: Observability

**Files:**
- bot/metrics.py

**Tasks:**
1. Prometheus metrics: updates_total, commands_total, callbacks_total, errors_total, active_users, api_latency, notifications_sent, auth_failures
2. structlog JSON logging to stdout
3. Health check endpoint (if webhook) or startup health log

**Acceptance:** Metrics exported, logs in JSON format

---

## Phase 5: Quality (T12-T13)

### T12: Tests

**Target:** 80%+ coverage

**Files:**
- bot/tests/conftest.py — fixtures (mock CRMClient, mock aiogram)
- bot/tests/test_auth.py — AuthMiddleware tests
- bot/tests/test_handlers/test_leads.py — lead handler tests
- bot/tests/test_handlers/test_clients.py
- bot/tests/test_services/test_crm_client.py — CRMClient tests
- bot/tests/test_services/test_permissions.py
- bot/tests/test_keyboards/test_leads.py

**Test Scenarios:**
1. Auth: valid user, invalid user, deleted user, expired cache
2. Permissions: admin can admin, viewer cannot create
3. Handlers: all commands return expected responses
4. FSM: create lead flow completes, /cancel works
5. CRMClient: retry on 503, error mapping, timeout handling
6. Notifications: poller sends to correct user
7. Pagination: first, middle, last page

---

### T13: Deployment

**Tasks:**
1. Create systemd service: /etc/systemd/system/telegram-bot.service
2. Create .env.example for bot/ directory
3. Add bot/requirements.txt
4. Deployment script: create_user, install_deps, enable_service
5. Production launch checklist

**Acceptance:** Bot starts as systemd service, survives reboot

---

## Deliverables

### Files Created

```
bot/
+-- app.py
+-- config.py
+-- metrics.py
+-- requirements.txt
+-- .env.example
|
+-- handlers/
|   +-- __init__.py
|   +-- start.py
|   +-- leads.py
|   +-- clients.py
|   +-- properties.py
|   +-- deals.py
|   +-- tasks.py
|   +-- admin.py
|
+-- keyboards/
|   +-- __init__.py
|   +-- main.py
|   +-- leads.py
|   +-- clients.py
|   +-- properties.py
|   +-- tasks.py
|
+-- services/
|   +-- __init__.py
|   +-- crm_client.py
|   +-- permissions.py
|   +-- notifications.py
|
+-- middleware/
|   +-- __init__.py
|   +-- auth.py
|   +-- request_context.py
|
+-- states/
|   +-- __init__.py
|   +-- lead.py
|   +-- task.py
|   +-- property.py
|
+-- schemas/
|   +-- __init__.py
|   +-- callbacks.py
|
+-- tests/
|   +-- __init__.py
|   +-- conftest.py
|   +-- test_auth.py
|   +-- test_handlers/
|   +-- test_services/
|   +-- test_keyboards/
```

### Files Modified

```
docs/adr/0014-telegram-staff-assistant-v1.md  (new)
docs/architecture/telegram_staff_assistant.md  (new)
docs/sprints/sprint_03.md                      (new)
docs/project_status.md                         (updated)
backend/requirements.txt                        (+ aiogram, httpx)
```

---

## Risks

| Risk | Mitigation | Owner |
|------|-----------|-------|
| API not available when bot starts | Health check before poll loop; graceful error messages | Backend |
| Callback_data 64 byte limit | Compact encoding; use data attributes for complex actions | Bot |
| Telegram ID changes after employee switches device | Admin can update telegram_id; /start re-auths | Admin |
| Rate limiting by Telegram | 30 req/min per user; batch notifications | Bot |
| FSM timeout mid-wizard | 10 min timeout -> cancel with warning; user data preserved | Bot |
| Notification spam (many leads arrive) | Rate limit 1 notification/5s per user; batch planned for S5 | Bot |

---

## Success Criteria

1. Employee opens Telegram -> /start -> main menu
2. Views new leads, assigns to self, qualifies, converts to client
3. Searches properties by address, views owner details
4. Creates task with FSM wizard, assignee receives notification
5. Changes deal status, all participants notified
6. All actions logged to audit with source_component=telegram_bot
7. No direct DB access from bot layer
8. 80%+ test coverage
