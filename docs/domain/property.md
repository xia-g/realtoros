# Property

Объект недвижимости — квартира, дом, коммерческое помещение, участок.

## Типы недвижимости

- apartment — квартира
- house — дом
- commercial — коммерческая
- land — участок
- townhouse — таунхаус
- penthouse — пентхаус

## Статусы

- available — доступен
- under_contract — в сделке
- sold — продан
- rented — сдан в аренду
- archived — архивный
- removed — снят с продажи

## Атрибуты

- id: UUID (PK)
- property_type: PropertyType
- status: PropertyStatus
- deal_type: DealType (sale|rent_short|rent_long|commercial)
- title: string
- description: text
- address: string
- area_total: float (общая площадь, м²)
- area_living: float (жилая площадь, м², опционально)
- rooms: int
- floor: int (опционально)
- floors_total: int (опционально)
- price: decimal (цена или арендная плата)
- price_currency: string (RUB|USD|EUR)
- price_per_meter: decimal (цена за м², вычисляемое)
- commission: decimal (комиссия агентства)
- owner_id: UUID (FK -> Client)
- photos: string[] (ссылки на файлы)
- documents: string[] (ссылки на документы)
- notes: text
- created_at: timestamp
- updated_at: timestamp

## Связи

- Belongs to Client (владелец)
- Has many Deal (участвует в сделках)
- Has many Document (документы объекта)
- Has many Task (задачи по объекту)

## Индексы

- status + deal_type — фильтрация по статусу и типу сделки
- property_type — поиск по типу
- address — полнотекстовый поиск
- price — сортировка по цене
- owner_id — все объекты владельца
- area_total — поиск по площади
- rooms — поиск по комнатам
