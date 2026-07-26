# Stream 1 — Organization Profile: Technical Design Proposal

```
Epic              3 — Accounting Compliance & Reporting
Stream            1 — Organization Profile
Phase             1 — Technical Design
Status            🟢 Approved (эталонный proposal)
Architecture      v3.0 (Platform FROZEN, Knowledge FROZEN)
Product Layer     Compliance (новый модуль)
Predecessors      Epic 1 (Intelligent Document Intake), Epic 2 (не реализован)
```

---

## 1. Scope / Goals

### Problem

Система не знает налогоплательщика. Существующая таблица `public.companies`
содержит юридические реквизиты (KPP, OGRN, банковские счета), но:

- Использует `id`, а не `organization_id` — несовместимо с ADR-005
- Не содержит полей, критичных для Compliance: `entity_type` (ИП/ООО),
  `has_employees`, `has_vat`, `reporting_period`
- Размазана между `public.companies` и `accounting.tax_regime` — два источника
- Завязана на `accounting` schema, хотя это общесистемные данные

### Goals

1. **Создать OrganizationProfile** — единую карточку организации для
   Compliance Layer, содержимое которой достаточно для Eligibility Engine,
   Rules Catalog, Dependency Engine
2. **Ввести organization_id** как единый идентификатор во всех Compliance
   сущностях (согласно ADR-005)
3. **Отделить Compliance-профиль** от юридических реквизитов компании
   (bank details, KPP, OGRN — остаются в `public.companies`)
4. **Обеспечить независимость** домена OrganizationProfile от Deal,
   Document, Compliance
5. **Определить Repository Contract** — стабильный интерфейс, от которого
   зависят Streams 2-11, а не от SQLAlchemy
6. **Определить стратегию совместимости** с существующей `public.companies`

### Non-goals (границы Scope)

- **Не CRUD юридических реквизитов** — bank details, KPP, OGRN остаются
  в `public.companies` (Product Layer не заменяет Platform)
- **Не миграция существующих данных** — `public.companies` продолжает
  работать для Accounting Layer
- **Не авторизация** — аутентификация/авторизация не входит в Stream 1
- **Не UI** — фронтенд будет в отдельном Stream

---

## 2. Domain Model

### OrganizationProfile (Core Domain Entity)

```python
@dataclass(frozen=True)
class OrganizationProfile:
    organization_id: UUID          # единый идентификатор (= organization_id, не id)
    name: str                      # ООО "Риэлторос" / ИП Иванов
    entity_type: EntityType        # ip | ooo | group | branch
    inn: str                       # ИНН (10 или 12 цифр)
    tax_regime: TaxRegime          # УСН6, УСН15, ОСНО, ПАТЕНТ
    has_employees: bool            # есть ли сотрудники
    has_vat: bool                  # есть ли НДС
    region_code: RegionCode        # нормализованный код региона
    reporting_period: ReportingPeriod  # monthly | quarterly | yearly
    settings: dict                 # только редко используемые параметры (см. принцип)
    version: int = 1               # оптимистичная блокировка / версионирование

    # Метаданные
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None  # audit: кто создал
    updated_by: str | None = None  # audit: кто изменил
    source: str | None = None      # audit: откуда пришли данные (import, api, override)
```

### Supporting Value Objects / Enums

```python
class EntityType(str, Enum):
    IP = "ip"          # Индивидуальный предприниматель
    OOO = "ooo"        # Общество с ограниченной ответственностью
    GROUP = "group"    # Группа компаний
    BRANCH = "branch"  # Филиал / обособленное подразделение

class TaxRegime(str, Enum):
    USN_6 = "usn_6"           # УСН "Доходы" 6%
    USN_15 = "usn_15"         # УСН "Доходы минус расходы" 15%
    OSNO = "osno"             # Общая система налогообложения
    PATENT = "patent"         # Патентная система
    ESHN = "eshn"             # Единый сельскохозяйственный налог
    SELF_EMPLOYED = "self_employed"  # Самозанятый (НПД)

class ReportingPeriod(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
```

### Supporting Value Objects (дополнительные)

```python
@dataclass(frozen=True)
class RegionCode:
    """Нормализованный код региона.

    Решает проблему нормализации: СПб, Санкт-Петербург, Saint Petersburg,
    78, RU-SPE — всё это один регион.

    Архитектурное решение:
    - Храним нормализованный код (OKATO / OKTMO / ISO 3166-2)
    - Расширяемость через список допустимых кодов
    - Отображение (display name) — дело UI / локализации
    """
    code: str                          # нормализованный код (например "78" или "RU-SPE")
    system: str = "okato"              # система кодирования: okato, oktmo, iso_3166_2

    def __post_init__(self):
        if not self.code or len(self.code) > 20:
            raise ValueError(f"Invalid region code: {self.code}")


# --- Принцип использования settings ---
# settings НЕ предназначен для обязательных бизнес-полей.
# Только для редко используемых, конфигурационных параметров,
# которые не требуют собственного поля в Domain Model.
# Пример: usn_rate, льготные ставки.
# Не заменяет Domain Model — если поле нужно в логике Eligibility Engine,
# Rules Catalog или Dependency Engine — оно должно быть отдельным полем.


# --- Архитектурный риск: reporting_period ---
# Текущее значение (monthly / quarterly / yearly) — упрощение.
# В реальности у разных отчётов (tax declaration, VAT, profit, insurance)
# периоды могут различаться. Возможно, reporting_period должен жить
# в Rules Catalog (Stream 2), а не в OrganizationProfile.
# Решение: оставляем здесь как временное поле, но помечаем как
# архитектурный риск для ревизии в Stream 2.
```

### Domain Boundaries

```
┌──────────────────────────────────────────────────────────────┐
│                    OrganizationProfile (этот Stream)          │
│                                                              │
│  НЕ ЗНАЕТ о:                                                  │
│    • Document / PDF                                          │
│    • Deal                                                    │
│    • Accounting Entry                                        │
│    • Business Event                                          │
│    • Compliance Rules                                        │
│    • Reports                                                 │
│                                                              │
│  Единственный downstream consumer:                            │
│    • Streams 2-11 читают OrganizationProfile через Repository │
│                                                              │
│  Не хранит:                                                   │
│    • Bank details (KPP, OGRN, расчётный счёт) — в companies  │
│    • CEO / contact info — в companies                         │
│    • Legal address — в companies                              │
│    • Platform metadata — в Platform Layer                     │
└──────────────────────────────────────────────────────────────┘
```

### Relationship to existing `public.companies`

```
public.companies (существующий)
  │
  ├── Содержит: юридические реквизиты (KPP, OGRN, bank, CEO, адреса)
  ├── PK: id (не organization_id)
  ├── Управляется: Platform / Accounting Layer
  └── Остаётся: без изменений

organization_profiles (НОВЫЙ — Product Layer, Compliance)
  │
  ├── Содержит: Compliance-значимые поля (tax_regime, entity_type, has_vat, ...)
  ├── PK: organization_id (= id из public.companies при импорте)
  ├── Управляется: Compliance Layer
  └── Синхронизация: начальный импорт + ручное создание (см. Migration Plan)
```

---

## 3. Invariants

### Domain invariants

| # | Инвариант | Проверка | Нарушение |
|:-:|:----------|:---------|:----------|
| 1 | `organization_id` — UUID, уникальный, не null | Domain constructor | ValueError |
|| 2 | `inn` — 10 цифр (ЮЛ) или 12 цифр (ИП) + контрольная сумма | `INNValidator.validate_checksum()` | InvalidInnError |
|| 3 | `inn` — уникален в пределах системы (опционально) | Repository | DuplicateInnError |
|| 4 | `entity_type` — только из EntityType enum | Pydantic/Typing | ValidationError |
|| 5 | `tax_regime` — только из TaxRegime enum | Pydantic/Typing | ValidationError |
|| 6 | `has_employees` → если `entity_type == "ip"`, может быть false | Business rule | — |
|| 7 | `organization_id` не изменяется после создания | Domain model (immutable PK) | — |
|| 8 | `name` — не пустой, не длиннее 500 символов | Validator | InvalidNameError |
|| 9 | `version` — монотонно возрастает при каждом update | Application Service (replace) | OptimisticLockError |
|| 10 | `archived_at` — если установлен, профиль считается неактивным | Repository/Service | — |

### System invariants

| # | Инвариант | Механизм |
|:-:|:----------|:---------|
| 9 | Все downstream сущности ссылаются на `organization_id` (не `id`, не `company_id`) | FK constraint in SQL |
| 10 | OrganizationProfile → BusinessEvent — 1:N по organization_id | FK |
| 11 | OrganizationProfile → OrganizationOverride — 1:N по organization_id | FK |
| 12 | OrganizationProfile → Task — 1:N по organization_id | FK |
| 13 | При удалении OrganizationProfile — каскадное поведение определяется политикой (soft delete / block) | Application policy |

---

## 4. Package Structure

```
backend/compliance/                          ← Product Layer модуль
├── __init__.py
│
├── domain/                                  ← Чистый Python, 0 dependencies
│   ├── __init__.py
│   ├── models.py                            ← OrganizationProfile dataclass
│   ├── enums.py                             ← EntityType, TaxRegime, ReportingPeriod
│   └── errors.py                            ← Domain-specific exceptions
│
├── application/                             ← Use cases (не зависит от DB/HTTP)
│   ├── __init__.py
│   ├── interfaces.py                        ← Repositoryポート (абстракции)
│   └── services.py                          ← OrganizationService (CRUD use cases)
│
├── infrastructure/                          ← External adapters
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── repository.py                    ← SQLAlchemy implementation
│   │   └── tables.py                        ← ORM model / table definitions
│   └── exceptions.py                        ← Infrastructure-level exceptions
│
├── api/                                     ← HTTP адаптер
│   ├── __init__.py
│   ├── routes.py                            ← FastAPI router
│   └── schemas.py                           ← Pydantic request/response models
│
└── tests/                                   ← Тесты
    ├── __init__.py
    ├── unit/
    │   ├── test_domain.py
    │   ├── test_services.py
    │   └── test_validators.py
    └── integration/
        ├── test_repository.py
        └── test_api.py
```

### Dependency flow

```
domain/  →  application/interfaces.py  →  infrastructure/persistence/
                                            api/routes.py
```

```
domain/ → application/ → infrastructure/  (внутренние зависимости)
domain/ → application/ ← api/             (inversion of control)
```

**Ключевое правило:** `domain/` и `application/interfaces.py` не импортируют
SQLAlchemy, FastAPI, asyncpg или любой другой внешний фреймворк.

---

## 5. Repository Interfaces

### IOrganizationProfileRepository (Application Port)

```python
# backend/compliance/application/interfaces.py

from abc import ABC, abstractmethod
from uuid import UUID
from compliance.domain.models import OrganizationProfile


class IOrganizationProfileRepository(ABC):
    """Repository contract — stable interface for all downstream streams.

    Streams 2-11 зависят ТОЛЬКО от этого интерфейса, а не от SQLAlchemy.
    """

    @abstractmethod
    async def get(self, organization_id: UUID) -> OrganizationProfile | None:
        """Get organization by ID. Returns None if not found."""
        ...

    @abstractmethod
    async def get_or_raise(self, organization_id: UUID) -> OrganizationProfile:
        """Get organization by ID. Raises OrganizationNotFoundError if not found."""
        ...

    @abstractmethod
    async def list(self, limit: int = 100, offset: int = 0) -> list[OrganizationProfile]:
        """List all organizations with pagination."""
        ...

    @abstractmethod
    async def add(self, profile: OrganizationProfile) -> OrganizationProfile:
        """Create a new organization profile. Raises on duplicate PK."""
        ...

    @abstractmethod
    async def update(self, profile: OrganizationProfile) -> OrganizationProfile:
        """Update an existing organization profile. Raises if not found."""
        ...

    @abstractmethod
    async def archive(self, organization_id: UUID) -> None:
        """Soft-delete — sets archived_at timestamp. Не физическое удаление."""
        ...

    @abstractmethod
    async def exists(self, organization_id: UUID) -> bool:
        """Check if organization exists (не archived)."""
        ...

    @abstractmethod
    async def find_by_inn(self, inn: str) -> OrganizationProfile | None:
        """Find organization by INN. Returns None if not found."""
        ...
```

### Design rationale

- **ABC, not Protocol** — язык реализации Python 3.13, ABC явнее для команды
- **async** — все операции асинхронные, т.к. бэкенд на FastAPI + asyncpg
- **Минимальный набор** — только CRUD + find_by_inn; query-специфичные методы
  добавляются по мере необходимости в downstream streams
- **Возвращает domain models** — не ORM-объекты, не dict. Потребители работают
  с `OrganizationProfile`, а не с SQLAlchemy `Row`
- **Не зависит от инфраструктуры** — ни один метод не импортирует asyncpg,
  SQLAlchemy, или любой другой фреймворк

---

## 6. Application Services

### Application Commands (чистые dataclass'ы — не Pydantic)

```python
# backend/compliance/application/commands.py
#
# ApplicationCommand — слой между API DTO и Domain.
# ApplicationService принимает Command, а не API-схему (Pydantic).
# Это изолирует Application от FastAPI/Pydantic и позволяет
# тестировать use cases без HTTP-контекста.

from dataclasses import dataclass, field
from uuid import UUID
from compliance.domain.enums import EntityType, TaxRegime, ReportingPeriod
from compliance.domain.models import RegionCode


@dataclass
class CreateOrganizationCommand:
    name: str
    entity_type: EntityType
    inn: str
    tax_regime: TaxRegime
    has_employees: bool = False
    has_vat: bool = False
    region_code: RegionCode | None = None
    reporting_period: ReportingPeriod = ReportingPeriod.YEARLY
    settings: dict = field(default_factory=dict)
    organization_id: UUID | None = None       # optional — generated if absent
    created_by: str | None = None              # audit
    source: str | None = "api"                 # audit


@dataclass
class UpdateOrganizationCommand:
    name: str | None = None
    entity_type: EntityType | None = None
    inn: str | None = None
    tax_regime: TaxRegime | None = None
    has_employees: bool | None = None
    has_vat: bool | None = None
    region_code: RegionCode | None = None
    reporting_period: ReportingPeriod | None = None
    settings: dict | None = None
    updated_by: str | None = None               # audit
```

### Clock / TimeProvider

```python
# backend/compliance/application/interfaces.py (дополнение)
#
# Clock (TimeProvider) — абстракция времени для тестируемости.
# Позволяет: (1) контролировать время в тестах, (2) не зависеть
# от datetime.now() в production, (3) воспроизводить баги по времени.

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """TimeProvider — inject вместо datetime.now()."""

    @abstractmethod
    def now(self) -> datetime:
        ...


class UTCClock(Clock):
    """Production implementation — returns UTC now."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
```

### OrganizationService

```python
# backend/compliance/application/services.py

from uuid import UUID, uuid4
from datetime import datetime, timezone
from dataclasses import replace

from compliance.domain.models import OrganizationProfile
from compliance.domain.enums import EntityType
from compliance.domain.errors import (
    OrganizationNotFoundError,
    DuplicateInnError,
    InvalidInnError,
)
from compliance.application.interfaces import IOrganizationProfileRepository, Clock
from compliance.application.commands import (
    CreateOrganizationCommand,
    UpdateOrganizationCommand,
)


class OrganizationService:
    """CRUD use cases for OrganizationProfile.

    Application Service управляет транзакцией: begin → repo.add/update/archive → commit.
    Repository НЕ делает commit() — это ответственность Application Service / Unit of Work.
    """

    def __init__(self, repo: IOrganizationProfileRepository, clock: Clock | None = None):
        self._repo = repo
        self._clock = clock or UTCClock()

    async def create(self, data: CreateOrganizationCommand) -> OrganizationProfile:
        """Create a new organization profile."""
        # 1. Validate INN checksum
        if not self._validate_inn(data.inn, data.entity_type):
            raise InvalidInnError(data.inn)

        # 2. Check uniqueness (optional — configurable)
        existing = await self._repo.find_by_inn(data.inn)
        if existing is not None:
            raise DuplicateInnError(data.inn)

        # 3. Build domain model using frozen dataclass
        now = self._clock.now()
        profile = OrganizationProfile(
            organization_id=data.organization_id or uuid4(),
            name=data.name,
            entity_type=data.entity_type,
            inn=data.inn,
            tax_regime=data.tax_regime,
            has_employees=data.has_employees,
            has_vat=data.has_vat,
            region_code=data.region_code,
            reporting_period=data.reporting_period,
            settings=data.settings,
            version=1,
            created_at=now,
            updated_at=now,
            created_by=data.created_by,
            updated_by=data.created_by,
            source=data.source,
        )

        # 4. Persist (add — не save)
        return await self._repo.add(profile)

    async def get(self, organization_id: UUID) -> OrganizationProfile:
        """Get organization by ID."""
        profile = await self._repo.get(organization_id)
        if profile is None:
            raise OrganizationNotFoundError(organization_id)
        return profile

    async def update(
        self,
        organization_id: UUID,
        data: UpdateOrganizationCommand,
    ) -> OrganizationProfile:
        """Update an existing organization profile.

        Использует dataclasses.replace() вместо setattr
        — frozen dataclass гарантирует immutable identity.
        """
        existing = await self._repo.get_or_raise(organization_id)
        updated = self._apply_updates(existing, data)
        return await self._repo.update(updated)

    async def archive(self, organization_id: UUID) -> None:
        """Soft-delete organization profile (archive, не физическое удаление)."""
        await self._repo.get_or_raise(organization_id)
        await self._repo.archive(organization_id)

    async def list(self, limit: int = 100, offset: int = 0) -> list[OrganizationProfile]:
        """List all organizations."""
        return await self._repo.list(limit=limit, offset=offset)

    # --- helpers ---

    def _validate_inn(self, inn: str, entity_type: str) -> bool:
        """Validate INN: length + optional checksum.

        TODO: INNValidator.validate_checksum() — реализовать после Stream 1,
        когда будет определён точный алгоритм проверки контрольной суммы.
        """
        if not inn.isdigit():
            return False
        if entity_type in ("ooo", "group", "branch"):
            return len(inn) == 10
        if entity_type == "ip":
            return len(inn) == 12
        return False

    def _apply_updates(
        self,
        existing: OrganizationProfile,
        data: UpdateOrganizationCommand,
    ) -> OrganizationProfile:
        """Apply partial updates using dataclasses.replace().

        Frozen dataclass → immutable identity: не setattr, а replace().
        Version increment — оптимистичная блокировка.
        """
        updates = {f.name: getattr(data, f.name)
                   for f in data.__dataclass_fields__.values()
                   if getattr(data, f.name) is not None}
        updates["version"] = existing.version + 1
        updates["updated_at"] = self._clock.now()
        if data.updated_by:
            updates["updated_by"] = data.updated_by
        return replace(existing, **updates)
```

### Request/Response DTOs (в `api/schemas.py`, не в application)

```python
class CreateOrganizationRequest(BaseModel):
    organization_id: UUID | None = None  # optional — generated if absent
    name: str = Field(..., min_length=1, max_length=500)
    entity_type: EntityType
    inn: str = Field(..., min_length=10, max_length=12, pattern=r"^\d+$")
    tax_regime: TaxRegime
    has_employees: bool = False
    has_vat: bool = False
    region_code: str = ""
    region_system: str = "okato"
    reporting_period: ReportingPeriod = ReportingPeriod.YEARLY
    settings: dict = Field(default_factory=dict)
    created_by: str | None = None
    source: str | None = "api"


class UpdateOrganizationRequest(BaseModel):
    name: str | None = None
    entity_type: EntityType | None = None
    inn: str | None = Field(None, min_length=10, max_length=12, pattern=r"^\d+$")
    tax_regime: TaxRegime | None = None
    has_employees: bool | None = None
    has_vat: bool | None = None
    region_code: str | None = None
    region_system: str | None = None
    reporting_period: ReportingPeriod | None = None
    settings: dict | None = None
    updated_by: str | None = None
```

---

## 7. Persistence Model

### Table: `organization_profiles`

Примечание: таблица создаётся в Product Layer, **не в Platform schema**.
Выбор схемы — `compliance` (новая schema, Product Layer).

```sql
CREATE TABLE compliance.organization_profiles (
    organization_id     UUID            NOT NULL DEFAULT gen_random_uuid(),
    name                VARCHAR(500)    NOT NULL,
    entity_type         VARCHAR(20)     NOT NULL CHECK (entity_type IN (
                            'ip', 'ooo', 'group', 'branch'
                        )),
    inn                 VARCHAR(12)     NOT NULL,
    tax_regime          VARCHAR(20)     NOT NULL CHECK (tax_regime IN (
                            'usn_6', 'usn_15', 'osno', 'patent', 'eshn', 'self_employed'
                        )),
    has_employees       BOOLEAN         NOT NULL DEFAULT false,
    has_vat             BOOLEAN         NOT NULL DEFAULT false,
    region_code         VARCHAR(20)     NOT NULL DEFAULT '',
    region_system       VARCHAR(20)     NOT NULL DEFAULT 'okato',
    reporting_period    VARCHAR(20)     NOT NULL DEFAULT 'yearly' CHECK (reporting_period IN (
                            'monthly', 'quarterly', 'yearly'
                        )),
    settings            JSONB           NOT NULL DEFAULT '{}',
    version             INTEGER         NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_by          VARCHAR(100),
    updated_by          VARCHAR(100),
    source              VARCHAR(50),
    archived_at         TIMESTAMPTZ,           -- soft-delete marker

    CONSTRAINT pk_organization_profiles PRIMARY KEY (organization_id),
    CONSTRAINT uq_organization_profiles_inn UNIQUE (inn)
);

-- Index for listing
CREATE INDEX idx_organization_profiles_name ON compliance.organization_profiles (name);

-- Index for region-based queries (Eligibility Engine)
CREATE INDEX idx_organization_profiles_region ON compliance.organization_profiles (region_code);
```

### ORM Mapping (SQLAlchemy)

```python
# backend/compliance/infrastructure/persistence/tables.py

from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OrganizationProfileTable(Base):
    __tablename__ = "organization_profiles"
    __table_args__ = {"schema": "compliance"}

    organization_id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    inn: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    tax_regime: Mapped[str] = mapped_column(String(20), nullable=False)
    has_employees: Mapped[bool] = mapped_column(Boolean, default=False)
    has_vat: Mapped[bool] = mapped_column(Boolean, default=False)
    region_code: Mapped[str] = mapped_column(String(20), default="")
    region_system: Mapped[str] = mapped_column(String(20), default="okato")
    reporting_period: Mapped[str] = mapped_column(String(20), default="yearly")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### Repository Implementation

```python
# backend/compliance/infrastructure/persistence/repository.py

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compliance.domain.models import OrganizationProfile
from compliance.domain.errors import OrganizationNotFoundError
from compliance.application.interfaces import IOrganizationProfileRepository
from compliance.infrastructure.persistence.tables import OrganizationProfileTable as Table


class SQLAlchemyOrganizationProfileRepository(IOrganizationProfileRepository):
    """SQLAlchemy implementation — единственное место, где ORM."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, organization_id: UUID) -> OrganizationProfile | None:
        row = await self._session.get(Table, organization_id)
        return self._to_domain(row) if row else None

    async def list(self, limit: int = 100, offset: int = 0) -> list[OrganizationProfile]:
        stmt = select(Table).offset(offset).limit(limit).order_by(Table.name)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_domain(r) for r in rows]

    async def add(self, profile: OrganizationProfile) -> OrganizationProfile:
        """Insert a new organization profile. Transaction управляется Application Service."""
        row = Table(**self._from_domain(profile))
        self._session.add(row)
        # no commit — transaction belongs to Application Service / Unit of Work
        return profile

    async def update(self, profile: OrganizationProfile) -> OrganizationProfile:
        """Update an existing organization profile. Raises if not found."""
        row = await self._session.get(Table, profile.organization_id)
        if not row:
            raise OrganizationNotFoundError(profile.organization_id)
        for field in self._FIELDS:
            setattr(row, field, getattr(profile, field))
        # no commit — transaction belongs to Application Service / Unit of Work
        return profile

    async def archive(self, organization_id: UUID) -> None:
        """Soft-delete — sets archived_at, не физическое удаление."""
        row = await self._session.get(Table, organization_id)
        if row:
            row.archived_at = datetime.now(timezone.utc)
            # no commit — transaction belongs to Application Service

    async def find_by_inn(self, inn: str) -> OrganizationProfile | None:
        stmt = select(Table).where(Table.inn == inn)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(row) if row else None

    # --- mapping helpers ---

    _FIELDS = [
        "name", "entity_type", "inn", "tax_regime", "has_employees",
        "has_vat", "region_code", "region_system", "reporting_period", "settings",
        "version", "created_at", "updated_at", "created_by", "updated_by",
        "source", "archived_at",
    ]

    @staticmethod
    def _to_domain(row: Table) -> OrganizationProfile:
        return OrganizationProfile(
            organization_id=row.organization_id,
            name=row.name,
            entity_type=row.entity_type,
            inn=row.inn,
            tax_regime=row.tax_regime,
            has_employees=row.has_employees,
            has_vat=row.has_vat,
            region_code=row.region_code if hasattr(row, 'region_code') else row.region,
            reporting_period=row.reporting_period,
            settings=row.settings,
            version=row.version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            created_by=row.created_by,
            updated_by=row.updated_by,
            source=row.source,
        )

    @staticmethod
    def _from_domain(p: OrganizationProfile) -> dict:
        return {
            "organization_id": p.organization_id,
            "name": p.name,
            "entity_type": p.entity_type.value if hasattr(p.entity_type, "value") else p.entity_type,
            "inn": p.inn,
            "tax_regime": p.tax_regime.value if hasattr(p.tax_regime, "value") else p.tax_regime,
            "has_employees": p.has_employees,
            "has_vat": p.has_vat,
            "region_code": p.region_code.code if hasattr(p.region_code, 'code') else p.region_code,
            "region_system": p.region_code.system if hasattr(p.region_code, 'system') else 'okato',
            "reporting_period": p.reporting_period.value if hasattr(p.reporting_period, "value") else p.reporting_period,
            "settings": p.settings,
            "version": p.version,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "created_by": p.created_by,
            "updated_by": p.updated_by,
            "source": p.source,
        }
```

---

## 8. API Contract

### Endpoints

```
GET    /api/v1/organizations                              → ListOrganizationsResponse
POST   /api/v1/organizations                              → OrganizationResponse
GET    /api/v1/organizations/{organization_id}             → OrganizationResponse
PUT    /api/v1/organizations/{organization_id}             → OrganizationResponse
POST   /api/v1/organizations/{organization_id}/archive     → 204 No Content  (soft-delete)
```

**Примечание:** следуем ADR-005 — все endpoint'ы имеют `organization_id`
в пути. Административный endpoint для списка/создания не содержит
`organization_id` (это исключение для admin-роли).

### Request/Response Schemas

```json
// POST /api/v1/organizations
// Request:
{
  "name": "ООО \"Риэлторос\"",
  "entity_type": "ooo",
  "inn": "7812345678",
  "tax_regime": "usn_6",
  "has_employees": true,
  "has_vat": false,
  "region_code": "78",
  "region_system": "okato",
  "reporting_period": "yearly",
  "settings": {
    "usn_rate": 6.0
  },
  "created_by": "user@example.com",
  "source": "api"
}

// Response (201):
{
  "organization_id": "a1b2c3d4-...",
  "name": "ООО \"Риэлторос\"",
  "entity_type": "ooo",
  "inn": "7812345678",
  "tax_regime": "usn_6",
  "has_employees": true,
  "has_vat": false,
  "region_code": "78",
  "region_system": "okato",
  "reporting_period": "yearly",
  "settings": {
    "usn_rate": 6.0
  },
  "version": 1,
  "created_at": "2026-07-23T10:00:00Z",
  "updated_at": "2026-07-23T10:00:00Z",
  "created_by": "user@example.com",
  "updated_by": "user@example.com",
  "source": "api"
}
```

```json
// GET /api/v1/organizations
// Response (200):
{
  "organizations": [
    {
      "organization_id": "...",
      "name": "ООО \"Риэлторос\"",
      "entity_type": "ooo",
      "inn": "7812345678",
      "tax_regime": "usn_6",
      "has_employees": true,
      "has_vat": false,
      "region_code": "78",
      "region_system": "okato",
      "reporting_period": "yearly",
      "settings": {},
      "version": 1,
      "created_at": "...",
      "updated_at": "...",
      "created_by": "...",
      "updated_by": "...",
      "source": "api"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### Error responses

```json
// 404 Organization Not Found
{
  "detail": "Organization not found",
  "code": "organization_not_found",
  "organization_id": "a1b2c3d4-..."
}

// 409 Duplicate INN
{
  "detail": "Organization with INN 7812345678 already exists",
  "code": "duplicate_inn",
  "inn": "7812345678"
}

// 422 Validation Error
{
  "detail": [
    {
      "loc": ["body", "inn"],
      "msg": "INN must be 10 digits for OOO",
      "type": "value_error"
    }
  ]
}
```

### Router registration

```python
# backend/compliance/api/routes.py

from fastapi import APIRouter, Depends
from uuid import UUID

router = APIRouter(prefix="/api/v1/organizations", tags=["Compliance Organizations"])

@router.get("")
async def list_organizations(
    limit: int = 100,
    offset: int = 0,
    service: OrganizationService = Depends(get_organization_service),
):
    ...

@router.post("", status_code=201)
async def create_organization(
    body: CreateOrganizationRequest,
    service: OrganizationService = Depends(get_organization_service),
):
    ...

@router.get("/{organization_id}")
async def get_organization(
    organization_id: UUID,
    service: OrganizationService = Depends(get_organization_service),
):
    ...

@router.put("/{organization_id}")
async def update_organization(
    organization_id: UUID,
    body: UpdateOrganizationRequest,
    service: OrganizationService = Depends(get_organization_service),
):
    ...

@router.post("/{organization_id}/archive", status_code=204)
async def archive_organization(
    organization_id: UUID,
    service: OrganizationService = Depends(get_organization_service),
):
    ...
```

---

## 9. Sequence Diagrams

### 9.1 Create Organization

```
Client                  API Router           OrganizationService        Repository          Database
  │                        │                        │                      │                   │
  │  POST /organizations   │                        │                      │                   │
  │───────────────────────▶│                        │                      │                   │
  │                        │  CreateOrganizationCmd  │                      │                   │
  │                        │───────────────────────▶│                      │                   │
  │                        │                        │                      │                   │
  │                        │                        │  validate_inn()      │                   │
  │                        │                        │  (Domain Service,    │                   │
  │                        │                        │   НЕ в Repository)   │                   │
  │                        │                        │                      │                   │
  │                        │                        │  find_by_inn(inn)    │                   │
  │                        │                        │──────────────────────▶─── SELECT ───────▶│
  │                        │                        │◀──── None ───────────│◀── None ──────────│
  │                        │                        │                      │                   │
  │                        │                        │  build domain model  │                   │
  │                        │                        │  (frozen dataclass)  │                   │
  │                        │                        │                      │                   │
  │                        │                        │  add(profile)        │                   │
  │                        │                        │──────────────────────▶─── INSERT ───────▶│
  │                        │                        │◀─── profile ─────────│◀── OK ────────────│
  │                        │                        │                      │                   │
  │                        │  OrganizationResponse   │                      │                   │
  │                        │◀───────────────────────│                      │                   │
  │◀─── 201 Created ───────│                        │                      │                   │
```

### 9.2 Get Organization (read by downstream Stream)

```
Downstream Stream      API Router           OrganizationService        Repository          Database
  (e.g. Stream 6)         │                        │                      │                   │
  │                        │                        │                      │                   │
  │  GET /orgs/{id}        │                        │                      │                   │
  │───────────────────────▶│                        │                      │                   │
  │                        │  get(org_id)            │                      │                   │
  │                        │───────────────────────▶│                      │                   │
  │                        │                        │  get(org_id)         │                   │
  │                        │                        │──────────────────────▶│─── SELECT ───────▶│
  │                        │                        │◀─ OrganizationProfile│◀── Row ───────────│
  │                        │                        │                      │                   │
  │                        │  OrganizationResponse   │                      │                   │
  │                        │◀───────────────────────│                      │                   │
  │◀─── 200 OK ───────────│                        │                      │                   │
```

### 9.3 Downstream Stream reads via Repository (internal)

```
Eligibility Engine        IOrganizationProfileRepository    SQLAlchemyRepo      Database
  │                               │                              │                │
  │  repo.get(org_id)             │                              │                │
  │──────────────────────────────▶│                              │                │
  │                               │  _session.get(Table, id)     │                │
  │                               │─────────────────────────────▶│─── SELECT ────▶│
  │                               │◀──── ORM Row ───────────────│◀── Row ────────│
  │                               │                              │                │
  │                               │  _to_domain(row)             │                │
  │                               │─────────────────────────────▶│                │
  │                               │◀── OrganizationProfile ─────│                │
  │                               │                              │                │
  │◀── OrganizationProfile ──────│                              │                │
  │                               │                              │                │
```

**Ключевой момент:** Downstream Streams (2-11) зависят только от
`IOrganizationProfileRepository` — интерфейса, не от SQLAlchemy.
Это позволяет:
- Менять ORM (SQLAlchemy → asyncpg → psycopg3) без затрагивания потребителей
- Тестировать с in-memory реализацией
- Добавлять кэширование прозрачно (декоратор/прокси)

---

## 10. Migration Plan

### Текущее состояние

В системе существует `public.companies` (Platform Layer):
- PK: `id` (не `organization_id`)
- Содержит: name, inn, kpp, ogrn, legal_address, actual_address, okved,
  bank_name, bank_bik, bank_account, phone, email, ceo_name, ceo_position,
  tax_regime, is_active
- Используется: Accounting Layer (`accounting.tax_regime` ссылается
  на `company_id`)

### Стратегия: Copy-on-write + coexistence

**Фаза 1 — создаём параллельную сущность (этот Stream):**

1. Создаём `compliance.organization_profiles` — новый Product Layer
2. Начальный импорт: для каждой активной записи из `public.companies`
   создаём OrganizationProfile с `organization_id = id`
3. Все новые организации создаются через `POST /api/v1/organizations`
   (в `compliance.organization_profiles`)
4. `public.companies` продолжает работать — Accounting Layer не трогаем

**Фаза 2 — синхронизация (после Stream 6):**

5. Если `public.companies` обновляется, синхронизируем OrganizationProfile
   через Business Event (Stream 3). Но не раньше, чем Streams 2-6 готовы.

**Фаза 3 — унификация (после всех Streams, опционально):**

6. `public.companies` → `compliance.organization_profiles` — объединение
   таблиц (если Platform Layer разрешит изменения)
7. Либо две таблицы живут параллельно: `public.companies` для юридических
   реквизитов, `compliance.organization_profiles` для Compliance-значимых
   полей

### Стратегия совместимости client_id / company_id

**В существующем коде:**

| Идентификатор | Где используется | Отношение к Compliance |
|:--------------|:-----------------|:-----------------------|
| `id` (public.companies) | Accounting Layer | `organization_id = id` при импорте |
| `client_id` | Clients module (CRM) | НЕ ИСПОЛЬЗУЕТСЯ в Compliance |
| `tenant_id` | Не найдено | Не применимо |

**Решение:**
- **Compliance Layer использует только `organization_id`**
- При начальном импорте: `organization_id = companies.id`
- Новые организации: `organization_id = uuid4()`

#### Проблема: синхронизация старых и новых идентификаторов

При начальном импорте `organization_id = companies.id`, но новые организации
получают `uuid4()`. Это создаёт риск рассинхронизации: в будущем `public.companies`
будет ссылаться на `id`, а Compliance — на `organization_id`.

**Решение через LegacyCompanyMapping:**

```python
# backend/compliance/domain/legacy_mapping.py
# Временная таблица-мост для обратной совместимости.

from dataclasses import dataclass
from uuid import UUID
from datetime import datetime


@dataclass(frozen=True)
class LegacyCompanyMapping:
    """Связь между legacy company_id и organization_id.

    Позволяет:
    - Находить OrganizationProfile по companies.id
    - Мигрировать ссылки в Streams 2-11 без изменения public.companies
    - Удалить mapping после полной унификации таблиц (Фаза 3)
    """
    organization_id: UUID
    legacy_company_id: UUID        # = companies.id при импорте
    created_at: datetime
```

**ADR-ссылка:** `ADR-007: Legacy identifier mapping` (создать после Stream 1).

- `client_id` остаётся в CRM-модуле — Compliance Layer его не знает
- Если в будущем понадобится связь Organization ↔ Client — через
  отдельную таблицу-мост, а не через переименование полей

---

## 11. Testing Strategy

### Unit tests (domain/)

| Тест | Что проверяет |
|:-----|:--------------|
| `test_create_organization_profile` | Создание с валидными полями |
| `test_invalid_inn_legal` | ИНН не 10 цифр для ЮЛ |
| `test_invalid_inn_ip` | ИНН не 12 цифр для ИП |
| `test_invalid_entity_type` | entity_type вне enum |
| `test_invalid_tax_regime` | tax_regime вне enum |
| `test_name_too_long` | name > 500 символов |
| `test_inn_uniqueness` | duplicate INN |
| `test_organization_id_immutable` | organization_id не меняется |

### Unit tests (application/)

| Тест | Что проверяет |
|:-----|:--------------|
| `test_create_organization_success` | Полный цикл create |
| `test_create_organization_duplicate_inn` | DuplicateInnError |
| `test_get_organization_not_found` | OrganizationNotFoundError |
| `test_update_organization` | Partial update |
| `test_archive_organization` | Soft-delete (archive) |

### Integration tests (infrastructure/)

| Тест | Что проверяет |
|:-----|:--------------|
| `test_repository_save_and_read` | SQLAlchemy CRUD |
| `test_repository_find_by_inn` | Поиск по ИНН |
| `test_repository_list_pagination` | Пагинация |
| `test_repository_archive` | Архивация (soft-delete) |
| `test_repository_inn_unique_violation` | DB-level unique constraint |

### API tests (e2e)

| Тест | Что проверяет |
|:-----|:--------------|
| `test_create_organization_endpoint` | POST 201 |
| `test_get_organization_endpoint` | GET 200 |
| `test_get_organization_404` | GET 404 |
| `test_update_organization_endpoint` | PUT 200 |
| `test_archive_organization_endpoint` | POST .../archive 204 |
| `test_list_organizations_pagination` | GET list + pagination |
| `test_create_organization_validation_error` | POST 422 |
| `test_create_organization_duplicate_inn` | POST 409 |

### Тестируем Repository Contract (critical for downstream)

```python
# Все downstream Streams тестируют через этот абстрактный тест:
class OrganizationProfileRepositoryTests(ABC):

    @abstractmethod
    def create_repo(self) -> IOrganizationProfileRepository:
        ...

    async def test_crud_cycle(self):
        repo = self.create_repo()
        profile = self._sample_profile()
        saved = await repo.add(profile)
        assert saved.organization_id == profile.organization_id
        loaded = await repo.get(profile.organization_id)
        assert loaded is not None
        assert loaded.name == profile.name
```

Каждая реализация репозитория (SQLAlchemy, in-memory, cache-proxy)
проходит один и тот же набор тестов. Streams 2-11 могут переиспользовать
эти тесты для своих кастомных реализаций.

---

## 12. Definition of Done

### Must have (критично для перехода к Stream 2)

- [ ] **Domain model** — `OrganizationProfile` dataclass с валидацией,
      `EntityType`, `TaxRegime`, `ReportingPeriod` enums
- [ ] **Repository interface** — `IOrganizationProfileRepository` в
      `application/interfaces.py`, без импорта SQLAlchemy
- [ ] **Clock/TimeProvider** — абстракция времени (`Clock` ABC) в
      `application/interfaces.py` для тестируемости
- [ ] **Versioning** — оптимистичная блокировка через `version` поле
      (increment при каждом update, проверка в Application Service)
- [ ] **Audit trail** — `created_by`, `updated_by`, `source` поля в
      Domain Model, Repository и API Contract
- [ ] **SQLAlchemy implementation** — `SQLAlchemyOrganizationProfileRepository`
      с mapping `_to_domain` / `_from_domain`
- [ ] **Миграция БД** — создание `compliance.organization_profiles` таблицы
      + индексы
- [ ] **API endpoints** — GET/POST/PUT /organizations + POST .../archive (soft-delete)
- [ ] **DI wiring** — FastAPI dependency injection для OrganizationService
- [ ] **Unit tests** — domain model, service layer (8+ тестов)
- [ ] **Integration tests** — repository with test DB (5+ тестов)
- [ ] **API tests** — e2e через HTTP (7+ тестов)
- [ ] **Все тесты проходят** — `pytest backend/compliance/tests/ -v`

### Should have (важно, но не блокирует Stream 2)

- [ ] **Начальный импорт** — скрипт миграции из `public.companies` в
      `compliance.organization_profiles`
- [ ] **In-memory repository** для тестов downstream Streams
- [ ] **API documentation** — OpenAPI/Swagger корректно отражает endpoint'ы
- [ ] **Logging** — ключевые операции (create, update, archive) логируются

### Must NOT have (запрещено)

- [ ] Зависимость OrganizationProfile от Deal, Document, или Compliance
- [ ] Импорт SQLAlchemy в `domain/` или `application/interfaces.py`
- [ ] Использование `company_id`, `client_id`, `tenant_id` вместо
      `organization_id` в Compliance-коде
- [ ] Изменение `public.companies` или `accounting.tax_regime`

---

## 13. Out of Scope

Что **НЕ входит** в Stream 1 и будет обработано в следующих Streams
(либо не будет никогда):

| Тема | Куда перенесено | Причина |
|:-----|:----------------|:--------|
| **UI для организаций** | Stream 9 (Reporting Workspace) или отдельный Stream UI | Compliance Layer — backend-first |
| **Юридические реквизиты** (KPP, OGRN, bank, адреса) | `public.companies` (Platform Layer) | Не Compliance-данные |
| **CEO / контакты** | `public.companies` | Не Compliance-данные |
| **Business Events** | Stream 3 | Отдельный модуль |
| **Rules Catalog** | Stream 2 | Зависит от organization_id |
| **Eligibility Engine** | Stream 5 | Зависит от OrganizationProfile + Rules |
| **Dependency Engine** | Stream 6 | Зависит от всего Foundation |
| **Compliance Timeline** | Stream 8 | Зависит от Engine Layer |
| **Simulation Engine** | Stream 7 | После Dependency Engine |
| **Explainability API** | Stream 11 | После всех Streams |
| **Auth / RBAC** | Platform Layer (отдельный Epic) | Не часть Compliance |
| **Multi-tenancy в Platform** | Platform Layer | ADR-005 для Compliance Layer |
| **Knowledge Layer интеграция** | Epic 1 / Отдельная задача | Platform frozen |
| **Аналитика / Дашборды** | Stream 9 или отдельный продукт | После Stream 11 |

---

## Приложение A: Сравнение существующей и новой модели

| Поле | `public.companies` (сущ.) | `compliance.organization_profiles` (нов.) | Комментарий |
|:-----|:-------------------------|:------------------------------------------|:------------|
| PK | `id` (UUID) | `organization_id` (UUID) | При импорте: `organization_id = id` |
| name | ✅ name | ✅ name | Копируется |
| inn | ✅ inn | ✅ inn | Копируется |
| entity_type | ❌ | ✅ entity_type | Новое поле |
| tax_regime | ✅ tax_regime (VARCHAR) | ✅ tax_regime (ENUM) | Валидируется |
| has_employees | ❌ | ✅ | Новое |
| has_vat | ❌ | ✅ | Новое |
| region_code | ❌ | ✅ `region_code` (VARCHAR(20)) | Нормализованный код региона |
| region_system | ❌ | ✅ `region_system` (VARCHAR(20), default 'okato') | Система кодирования: okato, oktmo, iso_3166_2 |
| reporting_period | ❌ | ✅ | Новое |
| version | ❌ | ✅ `version` (INTEGER, default 1) | Оптимистичная блокировка |
| archived_at | ❌ | ✅ `archived_at` (TIMESTAMPTZ, nullable) | Soft-delete маркер |
| created_by | ❌ | ✅ `created_by` (VARCHAR(100), nullable) | Audit: кто создал |
| updated_by | ❌ | ✅ `updated_by` (VARCHAR(100), nullable) | Audit: кто изменил |
| source | ❌ | ✅ `source` (VARCHAR(50), nullable) | Audit: откуда данные (import, api, override) |
| kpp | ✅ | ❌ | Остаётся в companies |
| ogrn | ✅ | ❌ | Остаётся в companies |
| bank_name / bank_bik / ... | ✅ | ❌ | Остаётся в companies |
| ceo_name / ceo_position | ✅ | ❌ | Остаётся в companies |
| settings | ❌ | ✅ (JSONB) | Новое |

## Приложение B: Эталонная структура для proposal других Streams

Этот proposal — **эталон** для Streams 2-11. Каждый proposal должен содержать
те же 13 разделов в том же порядке:

1. **Scope / Goals** — проблема, цели, non-goals
2. **Domain Model** — dataclass'ы, enums, границы
3. **Invariants** — domain + system invariants
4. **Package Structure** — tree + dependency flow
5. **Repository Interfaces** — ABC/Protocol, без фреймворков
6. **Application Services** — use cases + DTOs
7. **Persistence Model** — SQL schema + ORM mapping
8. **API Contract** — endpoints + request/response JSON
9. **Sequence Diagrams** — ключевые сценарии
10. **Migration Plan** — от существующего состояния
11. **Testing Strategy** — unit / integration / API / contract
12. **Definition of Done** — must / should / must-not
13. **Out of Scope** — что не входит и куда перенесено
