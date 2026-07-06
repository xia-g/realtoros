# Client

Клиент агентства — физическое или юридическое лицо.

## Типы клиентов

- buyer — покупатель
- seller — продавец
- tenant — арендатор (посуточная/долгосрочная)
- landlord — арендодатель
- investor — инвестор
- partner — партнёр

## Статусы

- lead — лид
- active — активный
- inactive — неактивный
- archived — архивный
- blacklisted — чёрный список

## Атрибуты

- id: UUID (PK)
- type: ClientType (buyer|seller|tenant|landlord|investor|partner)
- status: ClientStatus (lead|active|inactive|archived|blacklisted)
- full_name: string
- phone: string
- email: string (optional)
- telegram_id: string (optional)
- telegram_username: string (optional)
- source: string (referral|site|telegram|call|other)
- notes: text
- tags: string[]
- created_at: timestamp
- updated_at: timestamp

## Связи

- Has many ClientContact (контактные лица)
- Has many Deal (как участник сделок)
- Has many Communication (коммуникации с клиентом)
- Has many Document (документы клиента)
- Has many Task (задачи, связанные с клиентом)

## Индексы

- type + status — фильтрация по типу и статусу
- phone — поиск по телефону (уникальный)
- telegram_id — поиск по телеграму
- source — статистика по источникам
