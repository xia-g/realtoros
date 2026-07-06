# User

Пользователь системы — сотрудник агентства.

## Роли

- owner — собственник агентства (полный доступ)
- agent — риелтор
- admin — администратор (доступ к настройкам)
- accountant — бухгалтер (финансовые отчёты)
- manager — управляющий (назначено на будущее)

## Статусы

- active — активен
- inactive — неактивен (в отпуске)
- blocked — заблокирован

## Атрибуты

- id: UUID (PK)
- role: UserRole
- status: UserStatus
- full_name: string
- phone: string
- email: string
- telegram_id: string (опционально)
- telegram_username: string (опционально)
- telegram_chat_id: string (опционально)
- password_hash: string
- avatar: string (путь к файлу, опционально)
- settings: jsonb (персональные настройки)
- last_login: timestamp
- created_at: timestamp
- updated_at: timestamp

## Роли (справочник ролей)

Роли хранятся в отдельной таблице `roles` для гибкости:

- id: UUID (PK)
- name: string (owner|agent|admin|accountant|manager)
- permissions: jsonb (массив разрешений)
- description: string
- is_system: boolean (системная роль — нельзя удалить)
- created_at: timestamp

## Связи

- Has one Role
- Has many Task (созданные/назначенные)
- Has many Deal (как ответственный)
- Has many Communication (как создатель)
- Has many Document (как загрузивший)

## Индексы

- role — фильтрация по роли
- telegram_id — поиск по телеграму (уникальный)
- email — уникальный
- phone — уникальный
- status — активные пользователи
