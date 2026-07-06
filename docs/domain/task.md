# Task

Задача — единица работы для риелтора или администратора.

## Статусы

- pending — ожидает выполнения
- in_progress — в работе
- completed — выполнена
- cancelled — отменена

## Приоритеты

- low — низкий
- medium — средний
- high — высокий
- critical — критический

## Атрибуты

- id: UUID (PK)
- title: string
- description: text
- status: TaskStatus
- priority: TaskPriority
- task_type: string (call|meeting|document|show|payment|other)
- client_id: UUID (FK -> Client, nullable)
- deal_id: UUID (FK -> Deal, nullable)
- property_id: UUID (FK -> Property, nullable)
- assigned_to: UUID (FK -> User, nullable)
- created_by: UUID (FK -> User)
- due_date: timestamp (дедлайн)
- completed_at: timestamp (когда выполнена)
- completed_by: UUID (FK -> User, nullable)
- reminder: timestamp (напоминание, опционально)
- notes: text
- tags: string[]
- created_at: timestamp
- updated_at: timestamp

## Связи

- Belongs to Client (опционально)
- Belongs to Deal (опционально)
- Belongs to Property (опционально)
- Assigned to User
- Created by User

## Индексы

- status + assigned_to — текущие задачи пользователя
- due_date — просроченные задачи
- priority + status — горящие задачи
- client_id — все задачи по клиенту
- deal_id — все задачи по сделке
