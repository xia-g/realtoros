# Deal

Сделка — центральная сущность, связывающая клиентов и объект недвижимости.

## Типы сделок

- sale — купля-продажа
- rent_short — посуточная аренда
- rent_long — долгосрочная аренда
- commercial — коммерческая недвижимость

## Статусы

- negotiation — переговоры
- contract_signing — подписание договора
- deposit — внесение задатка/депозита
- legal_check — юридическая проверка
- payment — оплата
- closed — завершена
- cancelled — отменена

## Атрибуты

- id: UUID (PK)
- deal_type: DealType
- status: DealStatus
- property_id: UUID (FK -> Property)
- title: string (авто-генерация: "Покупка {адрес}")
- description: text
- price: decimal
- price_currency: string
- commission: decimal
- commission_percent: float
- deposit_amount: decimal (опционально)
- start_date: date
- end_date: date (опционально — для аренды)
- closing_date: date (дата закрытия)
- source: string (referral|site|direct|other)
- notes: text
- created_by: UUID (FK -> User)
- created_at: timestamp
- updated_at: timestamp

## Участники сделки (DealParticipant)

- id: UUID (PK)
- deal_id: UUID (FK -> Deal)
- client_id: UUID (FK -> Client)
- role: ParticipantRole
  - buyer — покупатель
  - seller — продавец
  - tenant — арендатор
  - landlord — арендодатель
  - agent — риелтор со стороны клиента
  - witness — свидетель

## Связи

- Belongs to Property
- Has many DealParticipant
- Has many Document
- Has many Communication
- Has many Task

## Индексы

- status + deal_type — фильтрация активных сделок
- property_id — все сделки по объекту
- client_id (через DealParticipant) — все сделки клиента
- start_date / closing_date — отчётность по датам
