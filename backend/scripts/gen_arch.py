#!/usr/bin/env python3
import os

def write_file(p, content):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        f.write(content.strip() + "\n")
    print(f"Wrote {p} ({len(content)} bytes)")

arch = """# Telegram Staff Assistant V1 — Architecture

**Date:** 2026-06-07
**Sprint:** 3
**Status:** Draft
**Editor:** Principal Architect
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

---

## 3. Folder Structure

```
bot/
+-- __init__.py
+-- app.py                          # Aiogram app factory
+-- config.py                       # Bot token, API base URL, admin IDs
|
+-- handlers/
|   +-- __init__.py
|   +-- start.py                    # /start — auth gate, main menu
|   +-- leads.py                    # /lead, /leads — list, card, actions
|   +-- clients.py                  # /client, /client_search — card, history
|   +-- properties.py               # /property — search, card
|   +-- deals.py                    # /deal — view, status change
|   +-- tasks.py                    # /task — FSM create, complete, reopen
|   +-- admin.py                    # /admin — broadcast, user mgmt
|
+-- keyboards/
|   +-- __init__.py
|   +-- main.py                     # Main menu ReplyKeyboard
|   +-- leads.py                    # Lead card InlineKeyboard
|   +-- clients.py                  # Client card InlineKeyboard
|   +-- properties.py               # Property card InlineKeyboard
|   +-- tasks.py                    # Task actions InlineKeyboard
|
+-- services/
|   +-- __init__.py
|   +-- crm_client.py               # CRMClient — httpx wrapper
|   +-- permissions.py              # Role/permission checks
|   +-- notifications.py            # Notification dispatcher + templates
|
+-- middleware/
|   +-- __init__.py
|   +-- auth.py                     # AuthMiddleware — telegram_id check
|   +-- request_context.py          # Inject audit metadata
|
+-- states/
|   +-- __init__.py
|   +-- lead.py                     # LeadCreateFSM (5 steps)
|   +-- task.py                     # TaskCreateFSM (4 steps)
|   +-- property.py                 # PropertyCreateFSM (future)
|
+-- schemas/
|   +-- __init__.py
|   +-- callbacks.py                # Typed callback data classes
|
+-- tests/
    +-- __init__.py
    +-- conftest.py
    +-- test_auth.py
    +-- test_handlers/
    +-- test_services/
    +-- test_keyboards/
```

---

## 4. Authentication

### /start Flow

```
User sends /start
  -> AuthMiddleware gets message.from_user.id
    -> CRMClient.get("/api/v1/users?telegram_id={tg_id}")
      -> Backend checks users.telegram_id
        -> Found: return User + role -> show main menu
        -> 404: "Вы не авторизованы. Обратитесь к администратору."
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User deleted from CRM | Next /start: 404 |
| Soft-deleted user | Auth rejects: "Учетная запись деактивирована" |
| Role changed | Next /start loads fresh role, menu adjusts |
| No telegram_id | Cannot auth until admin assigns |

---

## 5. Roles & Permissions

Uses existing `roles` table (JSONB permissions).

### Command Access Matrix

| Command | admin | manager | agent | viewer |
|---------|-------|---------|-------|--------|
| /start, /menu | Yes | Yes | Yes | Yes |
| /leads | Yes | Yes | Yes | Yes r/o |
| /lead_assign | Yes | Yes | self only | No |
| /lead_qualify | Yes | Yes | No | No |
| /lead_convert | Yes | Yes | No | No |
| /client_create | Yes | Yes | Yes | No |
| /deal_status | Yes | Yes | No | No |
| /task_create | Yes | Yes | Yes | No |
| /admin | Yes | No | No | No |

---

## 6. Main Menu

### Layout

Row 1: [Лиды] [Клиенты]
Row 2: [Объекты] [Сделки]
Row 3: [Задачи] [Отчеты]
Row 4: [Админ] (admin only)

### Navigation
- ReplyKeyboardMarkup, resize_keyboard=True
- Each action returns to module list or card
- "Назад" InlineKeyboard button on every card
- Main menu on /start, /menu, or after action completion

---

## 7. Lead Module

### Commands

| Command | Action |
|---------|--------|
| /leads | List paginated leads (filter: new first) |
| /lead {id} | View lead card |
| /lead_search {text} | Search by name/phone |
| /lead_assign {id} {uid} | Assign lead |
| /lead_qualify {id} | Qualify lead |
| /lead_convert {id} | Convert lead -> client |
| /lead_close {id} {reason} | Close lead |

### Lead Card

```
ЛИД #125
Иванов Петр Сергеевич
+7 (912) 345-67-89
Источник: telegram
Статус: qualifying
Приоритет: warm
Бюджет: 10-15 млн.
Ответственный: Сергей

[Назначить] [Квалифицировать] [Конвертировать] [Закрыть] [Назад]
```

### Action Flows

**Assign**: Select agent from list -> POST /api/v1/leads/{id}/assign
**Qualify**: Confirm if score < 0.5 -> POST /api/v1/leads/{id}/qualify
**Convert**: Optional deal creation -> POST /api/v1/leads/{id}/convert
**Close**: Choose reason (lost/spam) -> POST close

### FSM: Lead Create

```
/handle_new_lead
  Step 1: Name (required)
  Step 2: Phone (optional)
  Step 3: Budget (optional)
  Step 4: Property type
  Step 5: Notes (optional)
  Confirm: [Да] [Нет]
  -> POST /api/v1/leads
"""

write_file("/home/xiag/real-estate-os/docs/architecture/telegram_staff_assistant.md", arch)
print("Written, but will extend with more sections in next script")
