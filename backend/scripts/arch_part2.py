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
