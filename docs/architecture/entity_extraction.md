# Entity Extraction Subsystem

## Overview

Extracts structured entities from OCR text after document classification. Transforms raw Russian-language document text into typed, validated domain objects ready for database insertion.

```
OCR Pipeline → Document Classifier → Entity Extraction → Validation → Storage
```

## Entity Catalogue

| Entity | Source Document Types | Domain Model Mapping |
|--------|-----------------------|----------------------|
| Client | contract (all types), passport, power_of_attorney | `clients` table |
| Property | sale_contract, rental_contract, egrn_extract | `properties` table |
| Address | contract (all types), egrn_extract | part of `properties.address`, `clients` |
| Price | contract (all types), receipt, egrn_extract | part of `deals.price`, `properties.price` |
| Deal | contract (all types) | `deals` table |
| Date | contract (all types), passport, receipt, egrn_extract | various timestamp/date fields |
| Organization | contract (all types), power_of_attorney, receipt | `clients` (as legal entity) |

## Extraction Architecture

### Pipeline

```
OCR Text + Document Type + Layout Data
    │
    ▼
┌─────────────────────────────────────────────┐
│  Stage 1: Pattern-based Extraction           │
│  (regex + rule engine, 0 cost)              │
│                                             │
│  ├─ Passport series/number: \d{4}\s\d{6}    │
│  ├─ Prices: \d[\d\s]*[руб₽USD$EUR]         │
│  ├─ Dates: \d{2}\.\d{2}\.\d{4}             │
│  ├─ Phone: \+7\s?\d{3}\s?\d{7}            │
│  ├─ INN: \d{10,12}                          │
│  └─ Email: [\w.]+@[\w.]+\.\w+              │
│                                             │
│  Result: raw entity candidates + positions  │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Stage 2: LLM-based Extraction              │
│  (document-type-specific prompts)           │
│                                             │
│  ├─ Select prompt template by doc_type      │
│  ├─ Inject OCR text + layout hints          │
│  ├─ LLM returns typed JSON (Pydantic)       │
│  └─ Merge with pattern-based results        │
│                                             │
│  Models (by document complexity):           │
│  ├─ passport, receipt → Qwen Local          │
│  ├─ egrn_extract, power_of_attorney         │
│  │   → DeepSeek Flash                       │
│  └─ contract (all types) → DeepSeek Pro     │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Stage 3: Validation & Merging              │
│                                             │
│  ├─ Confidence threshold check              │
│  ├─ Cross-field consistency (e.g., price    │
│  │  match between contract and receipt)     │
│  ├─ Duplicate detection (same client in     │
│  │  multiple roles)                         │
│  ├─ Format normalization                    │
│  │  (phones: +7XXXXXXXXXX)                  │
│  │  (dates: ISO 8601)                       │
│  │  (prices: decimal)                       │
│  └─ Generate validation report              │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Stage 4: Human Review (if needed)          │
│                                             │
│  ├─ Entities with confidence < threshold    │
│  ├─ Conflicting extracted values            │
│  ├─ Missing required fields                 │
│  └─ Telegram notification for correction    │
└─────────────────────────────────────────────┘
    │
    ▼
Structured Output → Database Insert / Update
```

### Document-Type → Agent Mapping

Each document type uses a specialized extraction pattern:

```python
EXTRACTION_TEMPLATES = {
    "sale_contract": {
        "model": "deepseek-pro",         # complex legal text
        "entities": ["client", "property", "price", "deal", "date", "organization"],
        "prompt": "sale_contract_v1",
        "roles": ["seller", "buyer"],     # always two clients
        "required": ["price", "date", "property.address"],
    },
    "agency_contract": {
        "model": "deepseek-pro",
        "entities": ["client", "price", "deal", "date", "organization"],
        "prompt": "agency_contract_v1",
        "roles": ["principal", "agent"],
        "required": ["organization.name", "price.amount"],
    },
    "rental_contract": {
        "model": "deepseek-pro",
        "entities": ["client", "property", "price", "deal", "date"],
        "prompt": "rental_contract_v1",
        "roles": ["landlord", "tenant"],
        "required": ["deal.start_date", "price.amount"],
    },
    "passport": {
        "model": "qwen-local",            # simple, structured
        "entities": ["client"],
        "prompt": "passport_v1",
        "roles": ["identity_subject"],
        "required": ["client.full_name", "client.passport_number"],
    },
    "egrn_extract": {
        "model": "deepseek-flash",
        "entities": ["property", "address", "organization", "client"],
        "prompt": "egrn_extract_v1",
        "roles": ["owner"],
        "required": ["property.cadastral_number", "address.full"],
    },
    "receipt": {
        "model": "qwen-local",
        "entities": ["price", "date", "organization"],
        "prompt": "receipt_v1",
        "roles": [],
        "required": ["price.amount", "date.value"],
    },
    "power_of_attorney": {
        "model": "deepseek-flash",
        "entities": ["client", "organization", "date"],
        "prompt": "power_of_attorney_v1",
        "roles": ["principal", "representative"],
        "required": ["client.full_name", "date.value"],
    },
}
```

## JSON Schema — Extraction Output

### Top-Level Output

```python
# EntityExtractionResult — container for all extracted entities
{
    "document_id": "UUID",
    "document_type": "sale_contract",
    "extracted_at": "2026-06-07T12:00:00Z",
    "overall_confidence": 0.92,  # weighted average of all entities
    "entities": {
        "clients": [...],        # one or more clients
        "properties": [...],     # zero or one property
        "deals": [...],          # zero or one deal
        "organizations": [...],  # zero or more organizations
    },
    "dates": [...],             # all extracted dates with context
    "prices": [...],            # all extracted prices with context
    "addresses": [...],         # all extracted addresses
    "validation": {
        "passed": True,
        "errors": [],
        "warnings": [],
        "missing_required": [],
    },
}
```

### 1. Client Schema

```python
class ExtractedClient(BaseModel):
    """Client entity extracted from a document.

    Mapped to clients table on insertion. One document may contain
    multiple clients (e.g., buyer + seller in a sale contract).
    """

    # Identity
    full_name: str = Field(description="ФИО полностью")
    role: Literal["buyer", "seller", "tenant", "landlord",
                  "principal", "agent", "owner", "representative",
                  "identity_subject", "unknown"] = Field(
        description="Роль стороны в документе"
    )

    # Contacts
    phone: str | None = Field(
        pattern=r"^\+7\d{10}$",
        description="Телефон в формате +7XXXXXXXXXX",
    )
    email: str | None = Field(
        pattern=r"^[\w.]+@[\w.]+\.\w+$",
        description="Email адрес",
    )

    # Identity documents (from passport)
    passport_series: str | None = Field(
        pattern=r"^\d{4}$",
        description="Серия паспорта (4 цифры)",
    )
    passport_number: str | None = Field(
        pattern=r"^\d{6}$",
        description="Номер паспорта (6 цифр)",
    )
    passport_code: str | None = Field(
        description="Код подразделения (XXX-XXX)",
    )
    birth_date: str | None = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Дата рождения (ISO 8601)",
    )
    birth_place: str | None = Field(
        description="Место рождения",
    )

    # Legal entity fields (for organizations as clients)
    is_legal_entity: bool = False
    inn: str | None = Field(
        pattern=r"^\d{10,12}$",
        description="ИНН организации",
    )
    ogrn: str | None = Field(
        pattern=r"^\d{13,15}$",
        description="ОГРН организации",
    )
    legal_address: str | None = Field(
        description="Юридический адрес",
    )

    # Residency
    registration_address: str | None = Field(
        description="Адрес регистрации",
    )
    actual_address: str | None = Field(
        description="Фактический адрес проживания",
    )

    # From which part of the document this was extracted
    source_text_snippet: str | None = Field(
        max_length=200,
        description="Фрагмент OCR-текста, из которого извлечены данные",
    )

    # Metadata
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    extraction_method: Literal["pattern", "llm", "hybrid"] = "llm"
```

### 2. Property Schema

```python
class ExtractedProperty(BaseModel):
    """Property entity extracted from a document.

    Mapped to properties table. Includes both contract details
    and EGRN extract data.
    """

    # Type
    property_type: Literal[
        "apartment", "house", "commercial", "land",
        "townhouse", "penthouse", "parking", "unknown",
    ] = "unknown"

    # Cadastral (from EGRN)
    cadastral_number: str | None = Field(
        pattern=r"^\d{2}:\d{2}:\d{7}:\d{1,4}$",
        description="Кадастровый номер (XX:XX:XXXXXXX:XXXX)",
    )
    cadastral_value: float | None = Field(
        description="Кадастровая стоимость (руб)",
    )

    # Physical characteristics
    area_total: float | None = Field(
        gt=0, description="Общая площадь (м²)"
    )
    area_living: float | None = Field(
        gt=0, description="Жилая площадь (м²)"
    )
    rooms: int | None = Field(
        ge=1, description="Количество комнат"
    )
    floor: int | None = Field(
        ge=1, description="Этаж"
    )
    floors_total: int | None = Field(
        ge=1, description="Всего этажей"
    )
    material: str | None = Field(
        description="Материал стен (панель, кирпич, монолит, дерево)"
    )

    # Description from document
    title: str | None = Field(
        description="Название/краткое описание объекта"
    )
    description: str | None = Field(
        description="Полное описание из документа"
    )

    # For rentals: furniture, utilities
    is_furnished: bool | None = None
    utilities_included: bool | None = None

    # Source
    source_text_snippet: str | None = Field(max_length=200)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    extraction_method: Literal["pattern", "llm", "hybrid"] = "llm"
```

### 3. Address Schema

```python
class ExtractedAddress(BaseModel):
    """Structured address extracted from document text."""

    full: str = Field(
        description="Полный адрес одной строкой"
    )
    context: Literal[
        "property",          # адрес объекта недвижимости
        "registration",      # адрес регистрации клиента
        "legal",            # юридический адрес организации
        "actual",           # фактический адрес
        "unknown",
    ] = "unknown"

    # Structured components
    country: str = "Россия"
    region: str | None = Field(
        description="Регион / область / край"
    )
    city: str | None = Field(
        description="Населённый пункт (город, село, посёлок)"
    )
    district: str | None = Field(
        description="Район города или муниципальный район"
    )
    street: str | None = Field(
        description="Улица"
    )
    house_number: str | None = Field(
        description="Номер дома (может включать корпус/строение)"
    )
    apartment: str | None = Field(
        description="Номер квартиры или помещения"
    )
    postal_code: str | None = Field(
        pattern=r"^\d{6}$",
        description="Почтовый индекс",
    )

    # For EGRN / property registry
    cadastral_quarter: str | None = Field(
        description="Кадастровый квартал"
    )
    land_use_type: str | None = Field(
        description="Вид разрешённого использования"
    )

    # Metadata
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_text_snippet: str | None = Field(max_length=200)
    extraction_method: Literal["pattern", "llm", "hybrid"] = "llm"
```

### 4. Price Schema

```python
class ExtractedPrice(BaseModel):
    """Monetary amount extracted from document text."""

    amount: float = Field(
        gt=0, description="Числовое значение суммы"
    )
    currency: Literal["RUB", "USD", "EUR"] = "RUB"
    raw_text: str = Field(
        description="Исходный текст с ценой (e.g., '5 000 000 рублей')"
    )

    context: Literal[
        "sale_price",           # цена продажи
        "rent_price",           # арендная плата
        "deposit",              # задаток / депозит
        "commission",           # комиссия агентства
        "cadastral_value",      # кадастровая стоимость
        "penalty",              # неустойка / штраф
        "receipt_amount",       # сумма по квитанции
        "insurance",            # страховая сумма
        "unknown",
    ] = "unknown"

    period: Literal[
        "one_time",     # единоразово
        "monthly",      # в месяц
        "yearly",       # в год
        "per_meter",    # за м²
        "unknown",
    ] = "unknown"

    includes_vat: bool | None = Field(
        description="Цена включает НДС"
    )
    vat_rate: float | None = Field(
        ge=0, le=20, description="Ставка НДС (0, 10, 20%)"
    )

    # Metadata
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_text_snippet: str | None = Field(max_length=200)
    extraction_method: Literal["pattern", "llm", "hybrid"] = "llm"
```

### 5. Deal Schema

```python
class ExtractedDeal(BaseModel):
    """Transaction/deal entity extracted from a contract document."""

    deal_type: Literal[
        "sale", "rent_short", "rent_long", "commercial", "unknown",
    ] = "unknown"

    # Parties
    seller: str | None = Field(
        description="Продавец / арендодатель (ФИО или название)"
    )
    buyer: str | None = Field(
        description="Покупатель / арендатор (ФИО или название)"
    )

    # Financial
    price: float | None = Field(
        gt=0, description="Цена сделки"
    )
    price_currency: Literal["RUB", "USD", "EUR"] = "RUB"
    deposit: float | None = Field(
        ge=0, description="Сумма задатка / депозита"
    )
    commission: float | None = Field(
        ge=0, description="Комиссия агентства"
    )
    commission_percent: float | None = Field(
        ge=0, le=100, description="Комиссия в процентах"
    )
    payment_schedule: str | None = Field(
        description="График платежей (текстовое описание)"
    )

    # Dates
    start_date: str | None = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Дата начала сделки / договора",
    )
    end_date: str | None = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Дата окончания (для аренды)",
    )
    closing_date: str | None = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Дата закрытия / передачи права",
    )

    # Subject
    subject_property: str | None = Field(
        description="Объект сделки (кратко)"
    )
    terms: str | None = Field(
        description="Особые условия сделки"
    )

    # Source
    source_text_snippet: str | None = Field(max_length=200)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    extraction_method: Literal["pattern", "llm", "hybrid"] = "llm"
```

### 6. Date Schema

```python
class ExtractedDate(BaseModel):
    """Temporal entity extracted from document text."""

    value: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Дата в формате ISO 8601",
    )
    raw_text: str = Field(
        description="Исходный текст (e.g., '15 января 2026 года')"
    )

    context: Literal[
        "contract_date",        # дата заключения договора
        "start_date",           # дата начала
        "end_date",             # дата окончания
        "payment_date",         # дата платежа
        "birth_date",           # дата рождения
        "issue_date",           # дата выдачи (паспорт)
        "expiry_date",          # срок действия
        "registration_date",    # дата регистрации (Росреестр)
        "closing_date",         # дата закрытия сделки
        "unknown",
    ] = "unknown"

    is_range_start: bool = False
    is_range_end: bool = False

    # Metadata
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_text_snippet: str | None = Field(max_length=200)
    extraction_method: Literal["pattern", "llm", "hybrid"] = "llm"
```

### 7. Organization Schema

```python
class ExtractedOrganization(BaseModel):
    """Legal entity extracted from document text.

    Mapped to clients table as type='partner' or clients with
    is_legal_entity=True. Includes agencies, banks, notaries.
    """

    name: str = Field(
        description="Полное наименование организации"
    )
    short_name: str | None = Field(
        description="Краткое наименование / аббревиатура"
    )

    role: Literal[
        "agency",               # агентство недвижимости
        "bank",                 # банк (ипотека, расчётный счёт)
        "notary",               # нотариус
        "developer",            # застройщик
        "insurance",            # страховая компания
        "appraiser",            # оценщик
        "rosreestr",            # Росреестр
        "mfc",                  # МФЦ
        "other",
    ] = "other"

    # Registration
    inn: str | None = Field(
        pattern=r"^\d{10,12}$",
        description="ИНН",
    )
    kpp: str | None = Field(
        pattern=r"^\d{9}$",
        description="КПП",
    )
    ogrn: str | None = Field(
        pattern=r"^\d{13,15}$",
        description="ОГРН",
    )
    legal_address: str | None = Field(
        description="Юридический адрес"
    )

    # Banking
    bank_name: str | None = Field(
        description="Наименование банка (для расчётных счетов)"
    )
    bank_bik: str | None = Field(
        pattern=r"^\d{9}$",
        description="БИК банка",
    )
    bank_account: str | None = Field(
        pattern=r"^\d{20}$",
        description="Расчётный счёт (20 цифр)",
    )
    correspondent_account: str | None = Field(
        pattern=r"^\d{20}$",
        description="Корреспондентский счёт (20 цифр)",
    )

    # Contact
    phone: str | None = Field(
        pattern=r"^\+7\d{10}$",
        description="Контактный телефон",
    )
    email: str | None = Field(
        description="Email",
    )
    website: str | None = Field(
        description="Веб-сайт",
    )

    # Source
    source_text_snippet: str | None = Field(max_length=200)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    extraction_method: Literal["pattern", "llm", "hybrid"] = "llm"
```

## Validation Rules

### Per-Field Validation

```python
class EntityValidator:
    """Validates extracted entities before database insertion."""

    VALIDATION_RULES = {
        "client": {
            "full_name": {
                "required": True,
                "min_length": 5,
                "max_length": 255,
                "pattern": r"^[А-ЯЁA-Z][а-яёa-z]+(?:\s[А-ЯЁA-Z][а-яёa-z]+)+$",
                "error": "ФИО должно содержать минимум фамилию и имя",
            },
            "phone": {
                "required": False,
                "pattern": r"^\+7\d{10}$",
                "normalize": lambda v: re.sub(r"[\s\-\(\)]", "", v),
                "error": "Телефон должен быть в формате +7XXXXXXXXXX",
            },
            "passport_series": {
                "required": False,
                "pattern": r"^\d{4}$",
                "error": "Серия паспорта — 4 цифры",
            },
            "passport_number": {
                "required": False,
                "pattern": r"^\d{6}$",
                "error": "Номер паспорта — 6 цифр",
            },
            "inn": {
                "required": False,
                "pattern": r"^\d{10,12}$",
                "checksum": "inn",  # validate INN checksum
                "error": "ИНН должен содержать 10 или 12 цифр",
            },
        },
        "property": {
            "cadastral_number": {
                "required": False,
                "pattern": r"^\d{2}:\d{2}:\d{7}:\d{1,4}$",
                "error": "Неверный формат кадастрового номера (XX:XX:XXXXXXX:XXXX)",
            },
            "area_total": {
                "required": False,
                "gt": 0,
                "lt": 100000,
                "error": "Площадь должна быть положительной и < 100 000 м²",
            },
            "rooms": {
                "required": False,
                "ge": 1,
                "le": 100,
                "error": "Количество комнат от 1 до 100",
            },
        },
        "price": {
            "amount": {
                "required": True,
                "gt": 0,
                "le": 10_000_000_000,  # 10 млрд
                "error": "Сумма должна быть положительной",
            },
        },
        "deal": {
            "start_date": {
                "required": True,
                "type": "date",
                "not_in_future": False,
                "error": "Дата начала сделки обязательна",
            },
        },
        "address": {
            "full": {
                "required": True,
                "min_length": 10,
                "error": "Адрес должен содержать не менее 10 символов",
            },
        },
    }

    def validate(
        self, entity_type: str, data: dict
    ) -> ValidationResult:
        """Validate extracted entity against rules.

        Returns: ValidationResult(passed, errors, warnings, normalized_data)
        """
        errors = []
        warnings = []
        normalized = dict(data)

        rules = self.VALIDATION_RULES.get(entity_type, {})
        for field, rule in rules.items():
            value = data.get(field)

            # Required check
            if rule.get("required") and not value:
                errors.append({
                    "field": field,
                    "code": "required",
                    "message": rule["error"],
                })
                continue

            if not value:
                continue

            # Pattern check
            if "pattern" in rule and not re.match(rule["pattern"], str(value)):
                errors.append({
                    "field": field,
                    "code": "pattern",
                    "message": rule["error"],
                    "value": value,
                })

            # Numeric bounds
            if isinstance(value, (int, float)):
                if "gt" in rule and not value > rule["gt"]:
                    errors.append({"field": field, "code": "gt", ...})
                if "lt" in rule and not value < rule["lt"]:
                    errors.append({"field": field, "code": "lt", ...})

            # Normalize
            if "normalize" in rule:
                normalized[field] = rule["normalize"](value)

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data=normalized,
        )
```

### Cross-Entity Validation

Rules that span multiple entities:

```python
CROSS_VALIDATION_RULES = [
    # Rule 1: Deal price ≈ Property price (within 5%)
    {
        "id": "price_consistency",
        "check": lambda d: (
            abs(d["deal"].price - d["property"].price)
            / max(d["deal"].price, 0.01)
            < 0.05
        ),
        "entities": ["deal", "property"],
        "severity": "warning",
        "message": "Цена в договоре и цена объекта различаются более чем на 5%",
    },

    # Rule 2: Deal parties match extracted clients
    {
        "id": "party_match",
        "check": lambda d: all(
            any(p.full_name in c.full_name for c in d["clients"])
            for p in [d["deal"].seller, d["deal"].buyer]
            if p
        ),
        "entities": ["deal", "clients"],
        "severity": "error",
        "message": "Стороны сделки не найдены среди извлечённых клиентов: {missing}",
    },

    # Rule 3: Cadastral number appears in property and extract
    {
        "id": "cadastral_consistency",
        "check": lambda d: (
            d["property"].cadastral_number
            in d.get("address", {}).get("cadastral_quarter", "")
            if d["property"].cadastral_number
            else True
        ),
        "entities": ["property", "address"],
        "severity": "warning",
        "message": "Кадастровый номер не соответствует адресу",
    },

    # Rule 4: Dates are chronological
    {
        "id": "date_chronology",
        "check": lambda d: (
            parse(d["deal"].start_date) <= parse(d["deal"].closing_date)
            if d["deal"].start_date and d["deal"].closing_date
            else True
        ),
        "entities": ["deal"],
        "severity": "error",
        "message": "Дата начала сделки позже даты закрытия",
    },

    # Rule 5: Commission ≤ 100% of price
    {
        "id": "commission_bounds",
        "check": lambda d: d["deal"].commission <= d["deal"].price * 0.5,
        "entities": ["deal"],
        "severity": "error",
        "message": "Комиссия превышает 50% от цены сделки",
    },
]
```

### Required Fields Per Document Type

```python
REQUIRED_FIELDS = {
    "sale_contract": {
        "clients": ["full_name", "role"],
        "price": ["amount", "currency"],
        "deal": ["price", "start_date"],
        "address": ["full"],
    },
    "agency_contract": {
        "clients": ["full_name", "role"],
        "organization": ["name"],
        "price": ["amount"],
        "deal": ["commission"],
    },
    "rental_contract": {
        "clients": ["full_name", "role"],
        "property": ["property_type", "area_total"],
        "price": ["amount", "period"],
        "deal": ["start_date", "end_date"],
    },
    "passport": {
        "clients": ["full_name", "passport_series",
                     "passport_number", "birth_date"],
    },
    "egrn_extract": {
        "property": ["cadastral_number", "property_type", "area_total"],
        "address": ["full"],
        "organization": ["name"],
    },
    "receipt": {
        "price": ["amount"],
        "date": ["value"],
        "organization": ["name"],
    },
    "power_of_attorney": {
        "clients": ["full_name", "role"],
        "date": ["value"],
        "organization": ["name"],
    },
}
```

## Confidence Handling

### Per-Entity Confidence

```python
class EntityConfidence:
    """Determines confidence for each extracted entity field."""

    WEIGHTS = {
        "pattern": 0.60,   # regex patterns are strict but can't verify context
        "llm_low": 0.75,   # LLM extraction, low complexity (Qwen)
        "llm_medium": 0.85, # LLM extraction, medium complexity (DeepSeek Flash)
        "llm_high": 0.90,  # LLM extraction, high complexity (DeepSeek Pro)
        "hybrid": 0.88,    # pattern + LLM agree (boosted)
        "verified": 0.99,  # human-verified
    }

    def compute_field_confidence(
        self,
        method: str,
        llm_model: str | None = None,
        has_pattern_match: bool = False,
        pattern_confidence: float | None = None,
    ) -> float:
        base = self.WEIGHTS.get(method, 0.5)

        # Boost: pattern + LLM agree
        if has_pattern_match and method.startswith("llm"):
            base = min(base + 0.10, 0.98)

        # Boost: verified data
        if method == "verified":
            base = 0.99

        # Penalty: conflicting sources
        if has_pattern_match and pattern_confidence and pattern_confidence < 0.4:
            base = max(base - 0.15, 0.30)

        return round(base, 2)

    def compute_entity_confidence(self, fields: dict) -> float:
        """Weighted average of all field confidences."""
        if not fields:
            return 0.0
        confidences = [f.get("confidence", 0.0) for f in fields.values()]
        return sum(confidences) / len(confidences)
```

### Thresholds

```python
CONFIDENCE_THRESHOLDS = {
    "auto_accept": 0.85,    # ≥ 0.85: insert directly into DB
    "human_review": 0.60,   # 0.60–0.85: flag for operator check
    "reject": 0.40,         # < 0.40: reject, request new scan/upload
}

ACTION_MAP = {
    "auto_accept": {
        "action": "insert",
        "note": "Автоматически добавлено из документа {doc_id}",
    },
    "human_review": {
        "action": "flag_for_review",
        "note": "Требуется проверка: извлечено из {doc_id} с точностью {conf}",
        "notification": "telegram",  # send to agent's Telegram
    },
    "reject": {
        "action": "reject",
        "note": "Извлечение отклонено: точность {conf} ниже порога {threshold}",
        "notification": "telegram",
        "request": "Пожалуйста, загрузите документ в лучшем качестве",
    },
}
```

### Per-Field Confidence Example

```python
# Example: sale_contract extraction
{
    "clients": [
        {
            "full_name": {"value": "Иванов Иван Иванович", "confidence": 0.97},
            "role": {"value": "seller", "confidence": 0.92},
            "phone": {"value": "+79161234567", "confidence": 0.99},  # pattern match
            "passport_series": {"value": "4516", "confidence": 0.99},  # pattern match
            "passport_number": {"value": "123456", "confidence": 0.99}, # pattern match
            # Entity-level: weighted average = 0.97
        },
        {
            "full_name": {"value": "Петров Пётр Петрович", "confidence": 0.95},
            "role": {"value": "buyer", "confidence": 0.90},
            "phone": {"value": None, "confidence": 0.0},  # not found
            # Entity-level: weighted average = 0.62 (missing phone drags it down)
        },
    ],
    "property": {
        "property_type": {"value": "apartment", "confidence": 0.88},
        "area_total": {"value": 54.2, "confidence": 0.95},
        "rooms": {"value": 2, "confidence": 0.90},
        "floor": {"value": 5, "confidence": 0.85},
        "cadastral_number": {"value": "77:01:0004545:1234", "confidence": 0.99},
        # Entity-level: weighted average = 0.91
    },
    "price": {
        "amount": {"value": 8500000, "confidence": 0.99},  # pattern + LLM agree
        "currency": {"value": "RUB", "confidence": 0.99},
        "period": {"value": "one_time", "confidence": 0.95},
        # Entity-level: weighted average = 0.98
    },
    "overall_confidence": 0.87,  # weighted average across all entities
}
```

### Confidence Escalation

```
Entity Confidence
    │
    ├─ ≥ 0.85 ──→ Auto-accept: insert into DB
    │              Add source_note linking to document
    │
    ├─ 0.60–0.84 → Human review: flag for operator
    │              Send Telegram notification
    │              Show extracted values vs OCR snippet
    │
    ├─ 0.40–0.59 → Low confidence: suggest re-upload
    │              Store in draft state
    │              Do NOT update existing records
    │
    └─ < 0.40 ──→ Reject: request new scan/photo
                   Provide guidance (better lighting, etc.)
```

## Data Storage

### New Table: `extracted_entities`

```sql
CREATE TABLE extracted_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,

    -- Full extraction result (JSON)
    extraction_data JSONB NOT NULL DEFAULT '{}',
    -- Structure per schema above

    -- Confidence
    overall_confidence FLOAT NOT NULL DEFAULT 0.0,
    entity_confidences JSONB NOT NULL DEFAULT '{}',
    -- e.g. {"clients": 0.85, "property": 0.91, "price": 0.98}

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | auto_accepted | human_review | rejected

    validation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending | passed | warnings | errors

    validation_report JSONB DEFAULT '{}',
    -- {errors: [...], warnings: [...], missing_required: [...]}

    -- Audit
    extraction_model VARCHAR(50) NOT NULL,
    extraction_duration_ms INTEGER,
    created_by UUID REFERENCES users(id),
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'auto_accepted', 'human_review', 'rejected', 'applied')
    ),
    CONSTRAINT valid_validation CHECK (
        validation_status IN ('pending', 'passed', 'warnings', 'errors')
    )
);

-- Indexes
CREATE INDEX idx_extracted_entities_document
    ON extracted_entities(document_id);
CREATE INDEX idx_extracted_entities_status
    ON extracted_entities(status);
CREATE INDEX idx_extracted_entities_confidence
    ON extracted_entities(overall_confidence);
CREATE INDEX idx_extracted_entities_doc_type
    ON extracted_entities(document_type);
```

### Integration with Domain Model

```
documents
    │ (one document → one extraction)
    ▼
extracted_entities  (this table — stores the raw extraction result)
    │
    ├──(applied)──► clients  (new or matched existing)
    ├──(applied)──► properties  (new)
    ├──(applied)──► deals  (new)
    └──(applied)──► documents_metadata  (dates, prices, organizations)
```

When an extraction is `applied`:
1. New client records are created or matched by `full_name + phone`
2. New property records are created or matched by `cadastral_number`
3. New deal records are created with FKs to client and property
4. Organizations are stored with `clients.type = 'partner'`
5. All records link back to the source document

## Extraction Module Interface

```python
class EntityExtractor:
    """Main orchestrator for entity extraction."""

    def __init__(self):
        self.pattern_extractor = PatternExtractor()
        self.llm_extractor = LLMExtractor()
        self.validator = EntityValidator()

    async def extract(
        self,
        document_id: str,
        document_type: str,
        ocr_text: str,
        layout: dict | None = None,
    ) -> ExtractionResult:
        """Run full extraction pipeline for one document."""

        # 1. Select template
        template = EXTRACTION_TEMPLATES[document_type]

        # 2. Stage 1: Pattern-based extraction
        pattern_results = self.pattern_extractor.extract(
            ocr_text, template.entities
        )

        # 3. Stage 2: LLM extraction
        llm_results = await self.llm_extractor.extract(
            ocr_text=ocr_text,
            document_type=document_type,
            template=template,
            layout=layout,
            pattern_hints=pattern_results,  # inject pattern matches as hints
        )

        # 4. Merge: pattern + LLM
        merged = self._merge_results(pattern_results, llm_results)

        # 5. Validate
        validation = self.validator.validate_all(merged, document_type)

        # 6. Compute confidence
        confidence = self._compute_overall_confidence(merged)

        return ExtractionResult(
            document_id=document_id,
            document_type=document_type,
            entities=merged,
            validation=validation,
            overall_confidence=confidence,
            status=self._determine_status(confidence, validation),
        )

    def _merge_results(
        self, pattern: dict, llm: dict
    ) -> dict:
        """Merge pattern + LLM results.

        - If pattern and LLM agree → use LLM value, boost confidence
        - If pattern has a value LLM missed → add with lower confidence
        - If LLM has a value pattern missed → use LLM value
        - If they conflict → prefer LLM, flag for review
        """
        ...

    def _determine_status(
        self, confidence: float, validation: ValidationResult
    ) -> str:
        if validation.has_errors():
            return "human_review"
        if confidence >= 0.85:
            return "auto_accepted"
        if confidence >= 0.60:
            return "human_review"
        if confidence >= 0.40:
            return "pending"
        return "rejected"
```

## Performance Targets

| Metric | Target |
|--------|--------|
| End-to-end extraction latency (simple) | < 5 sec (passport, receipt) |
| End-to-end extraction latency (complex) | < 20 sec (contract) |
| Pattern stage coverage | 30–40% of fields |
| LLM stage coverage (after patterns) | 85–95% of fields |
| Extraction accuracy (auto-accepted) | > 90% |
| Extraction accuracy (after review) | > 99% |
| Human review rate | < 15% of extractions |
| Duplicate detection recall | > 95% |

## Error Handling

| Failure Mode | Handler |
|--------------|---------|
| LLM returns invalid JSON | Retry once with stricter prompt |
| LLM timeout (> 30 sec) | Use pattern-only results, flag for review |
| Pattern extraction empty | Skip to LLM-only extraction |
| Validation errors | Flag for human review, do not auto-apply |
| Duplicate client detected (by phone) | Merge flag: update existing or create new |
| Conflicting extracted values | Store both with confidences, flag for review |
| Missing required fields | Reject extraction, request complete document |

## Related Documentation

- `docs/architecture/ocr_layer.md` — upstream OCR pipeline
- `docs/architecture/document_classifier.md` — upstream document classification
- `docs/domain/domain_model.md` — core entities being extracted
- `docs/domain/database_schema_v1.md` — target database tables
- `docs/development_rules.md` — AI model selection guidelines
- `docs/adr/0005-document-classifier.md` — ADR for classification strategy
