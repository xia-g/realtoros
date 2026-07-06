# Communication

Коммуникация — запись любого взаимодействия с клиентом или участником сделки.

## Типы коммуникаций

- call — телефонный звонок
- email — email-переписка
- telegram — Telegram сообщение
- whatsapp — WhatsApp сообщение
- meeting — личная встреча
- site_message — сообщение с сайта
- note — внутренняя заметка

## Направления

- incoming — входящее
- outgoing — исходящее

## Атрибуты

- id: UUID (PK)
- communication_type: CommunicationType
- direction: Direction (incoming|outgoing)
- client_id: UUID (FK -> Client, nullable)
- deal_id: UUID (FK -> Deal, nullable)
- subject: string (тема)
- content: text
- duration: int (секунды — для звонков)
- contact: string (номер телефона / email / telegram username)
- assigned_to: UUID (FK -> User, nullable)
- is_important: boolean
- tags: string[]
- created_by: UUID (FK -> User)
- created_at: timestamp
- updated_at: timestamp

## Связи

- Belongs to Client (опционально)
- Belongs to Deal (опционально)
- Created by User
- Assigned to User (опционально)

Хотя бы одна из FK (client_id, deal_id) должна быть заполнена.

## Индексы

- client_id — история коммуникаций с клиентом
- deal_id — все коммуникации по сделке
- communication_type + created_at — лента по типу
- assigned_to — незакрытые задачи пользователя
