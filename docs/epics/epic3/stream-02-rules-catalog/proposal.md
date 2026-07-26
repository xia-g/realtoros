# Stream 2 — Rules Catalog: Technical Design Proposal

```yaml
Epic              3 — Accounting Compliance & Reporting
Stream            2 — Rules Catalog
Phase             1 — Technical Design
Status            🔵 In Review
Architecture      v3.0 (Platform FROZEN, Knowledge FROZEN)
Product Layer     Compliance (новый модуль)
Predecessors      Stream 1 — Organization Profile (commit 97504af)
Dependencies      IOrganizationProfileRepository (Stream 1)
```

---

## 1. Scope / Goals

### Problem

Система не знает, какие налоги и отчёты применимы к организации. Сейчас:

- Tax regime (УСН6, ОСНО, Патент) хранится в `OrganizationProfile`, но **сами правила** — что отчитываться, когда платить, какие требования — нигде не определены
- Изменения законодательства (новая ставка УСН, новый отчёт) требуют изменения кода, а не конфигурации
- Организации с одинаковым tax regime получают одинаковый набор правил, но некоторые могут иметь **специфические требования** (льготы, региональные особенности)
- Нет единого источника правды для: "какие отчёты сдаёт УСН 6% в 2026 году"

### Goals

1. **Создать Rules Catalog** — единый реестр всех Compliance-правил (налоговые, отчётные, применимости)
2. **Определить ComplianceRule** как центральный объект с Rule → RuleVersion → EffectivePeriod
3. **Реализовать двухуровневую модель:** Default Rules (YAML/JSON в Git) + Organization Overrides (Database)
4. **Определить Rule Resolver** — механизм, который для данной организации возвращает применимые правила с учётом Overrides
5. **Реализовать RequirementExpression** — AST для ALL/ANY/NOT композиции условий
6. **Реализовать DueRule** — гибкий DSL для сроков (offset/cron/expression)
7. **Обеспечить Rule Evaluation Trace** — структурированное дерево результатов оценки
8. **Реализовать Rules Catalog Validation** — проверка при старте (циклы, ссылки, перекрытия)
9. **Обеспечить интеграцию** с существующим `IOrganizationProfileRepository` (Stream 1)

### Non-goals (границы Scope)

- **Не реализация Eligibility Engine** — Stream 5; Stream 2 только описывает правила, но не решает "должен ли отчёт существовать?"
- **Не реализация Dependency Engine** — Stream 6; Stream 2 только предоставляет правила и их трассировку
- **Не UI для редактирования правил** — будет в отдельном инструменте (Git для Default, Admin UI для Overrides)
- **Не авторизация** — аутентификация/авторизация не входит в Stream 2
- **Не миграция существующих правил** — первая загрузка Default Rules из Git — начальная инициализация
- **Не Business Events** — Stream 3; изменение правил не порождает события в этом Stream'е
- **Не кэширование результатов** — Stream 5 (Eligibility Engine) займётся кэшированием

---

## 2. Domain Model

### 2.1 Central Entity: ComplianceRule

```python
@dataclass(frozen=True)
class RuleCode:
    """Type-safe rule identifier (e.g., 'usn_declaration', 'vat_return')."""
    code: str

    def __post_init__(self):
        if not self.code or len(self.code) > 100:
            raise ValueError(f"Invalid rule code: {self.code}")
        if not self.code.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Rule code must be alphanumeric with _/-: {self.code}")


class RuleType(str, Enum):
    TAX = "tax"                  # Налоговое правило (ставка, льгота)
    REPORTING = "reporting"      # Отчётное правило (декларация, расчёт)
    ELIGIBILITY = "eligibility"  # Правило применимости (кто должен сдавать)
    DUE = "due"                  # Правило срока (когда сдавать)


class RuleStatus(str, Enum):
    DRAFT = "draft"              # Черновик — можно редактировать
    PUBLISHED = "published"      # Опубликовано — immutable
    DEPRECATED = "deprecated"    # Заменено/устарело — не применяется, но сохраняется
    ARCHIVED = "archived"        # Архивировано — удалено из активного каталога


@dataclass(frozen=True)
class ComplianceRule:
    """Центральный объект Rules Catalog.

    Rule — это абстрактное описание требования/нормы.
    Одна Rule может иметь несколько версий (RuleVersion) с разными периодами действия.
    Rule НЕ ИМЕЕТ привязки к организации — это общесистемное определение.

    Правила бывают:
    - TaxRule: ставка налога, льгота, порядок расчёта
    - ReportingRule: обязанность сдать отчёт
    - EligibilityRule: условие применимости (кто должен?)
    - DueRule: срок сдачи
    """

    # ── Identity ─────────────────────────────────────────────────
    rule_code: RuleCode          # уникальный код: "usn_declaration"
    rule_type: RuleType          # tax / reporting / eligibility / due
    name: str                    # "Декларация по УСН"
    description: str             # пояснение

    # ── Category & Tags ──────────────────────────────────────────
    category: str = ""           # "tax", "vat", "insurance", "statistics"
    tags: tuple[str, ...] = ()   # ["yearly", "federal", "simplified"]

    # ── Lifecycle ─────────────────────────────────────────────────
    status: RuleStatus = RuleStatus.DRAFT
    created_at: datetime
    updated_at: datetime
    created_by: str              # автор правила
    updated_by: str              # кто последним изменил

    # ── Versioning ───────────────────────────────────────────────
    # Текущая версия (latest). История — в RuleVersion.
    # После PUBLISHED — immutable. Только через RuleVersion.
    current_version: RuleVersion | None = None

    def publish(self, *, published_by: str, effective_from: date,
                effective_to: date | None = None) -> ComplianceRule:
        """Publish the current draft as an immutable version."""
        ...

    def deprecate(self, *, updated_by: str) -> ComplianceRule:
        """Mark as deprecated (will be replaced by another rule)."""
        ...
```

### 2.2 Rule Versioning

```python
@dataclass(frozen=True)
class RuleVersion:
    """Иммутабельная версия правила.

    После публикации RuleVersion НИКОГДА не изменяется.
    Любое изменение → новая RuleVersion.
    История версий — append-only.

    Каждая версия действительна в период [effective_from, effective_to).
    """

    # ── Identity ─────────────────────────────────────────────────
    version_id: UUID             # уникальный ID версии
    rule_code: RuleCode          # ссылка на родительское правило
    version_number: int          # 1, 2, 3... монотонно возрастает

    # ── Effective Period ─────────────────────────────────────────
    effective_from: date         # с какой даты действует
    effective_to: date | None    # до какой даты (None = бессрочно)

    # ── Rule Content ─────────────────────────────────────────────
    # Что именно проверяется/требуется
    requirement_expression: RequirementExpression  # AST для ALL/ANY/NOT/FACT

    # Когда нужно сдать/оплатить
    due_rule: DueRule            # гибкий DSL для сроков

    # ── Applicability ────────────────────────────────────────────
    # Какие организации подпадают под правило
    applies_to_tax_regimes: frozenset[TaxRegime]      # УСН6, ОСНО...
    applies_to_entity_types: frozenset[EntityType]     # ip, ooo...
    applies_to_regions: frozenset[str] | None = None   # None = все регионы
    applies_to_has_employees: bool | None = None       # None = не важно

    # ── Frequency ────────────────────────────────────────────────
    frequency: str = "yearly"    # monthly, quarterly, yearly, one-time

    # ── Metadata ─────────────────────────────────────────────────
    source: str = "default"      # default | manual | import | law
    reference_law: str = ""      # ссылка на НПА: "НК РФ ст.346.23"
    change_reason: str = ""      # причина изменения: "закон №..."

    # ── Immutability ─────────────────────────────────────────────
    published_at: datetime
    published_by: str
```

### 2.3 RequirementExpression (AST)

```python
@dataclass(frozen=True)
class RequirementExpression:
    """AST для композиции условий.

    Примеры:
      ALL(revenue_posted, period_closed, payroll_posted)
      ANY(revenue_posted, payment_received)
      ALL(ANY(revenue_posted, payment_received), period_closed)
      NOT(revenue_posted)
    """

    MAX_EXPRESSION_DEPTH: int = 32  # максимальная глубина вложенности AST

    expression_type: Literal["ALL", "ANY", "NOT", "FACT"]
    fact_code: str | None = None         # для FACT — какой бизнес-факт
    children: tuple["RequirementExpression", ...] = ()  # для ALL/ANY/NOT
    criticality: str = "required"        # critical | required | optional | informational
    notes: str = ""                      # пояснение для бухгалтера

    def __post_init__(self):
        if self.expression_type == "FACT":
            if not self.fact_code:
                raise ValueError("FACT expression must have a fact_code")
            if self.children:
                raise ValueError("FACT expression must not have children")
        elif self.expression_type in ("ALL", "ANY", "NOT"):
            if not self.children:
                raise ValueError(f"{self.expression_type} must have at least one child")
            if self.fact_code:
                raise ValueError(f"{self.expression_type} must not have fact_code")
        elif self.expression_type == "NOT":
            if len(self.children) != 1:
                raise ValueError("NOT must have exactly one child")

        # Max depth check: рекурсивно проверяем глубину
        if self._compute_depth() > self.MAX_EXPRESSION_DEPTH:
            raise ValueError(
                f"Expression exceeds max depth of {self.MAX_EXPRESSION_DEPTH}"
            )

    def _compute_depth(self) -> int:
        """Рекурсивно вычисляет глубину AST."""
        if not self.children:
            return 1
        return 1 + max(child._compute_depth() for child in self.children)
```

### 2.4 DueRule (Flexible Deadline DSL)

```python
@dataclass(frozen=True)
class DueRule:
    """Гибкий DSL для сроков сдачи.

    Поддерживает три формата:
    - offset: "+3M 25d"  → через 3 месяца, 25-го числа
    - expression: "25th of month after quarter" → естественный язык
    - cron: "0 0 25 3 *" → cron-подобный (для сложных случаев)
    """

    rule_type: Literal["offset", "expression", "cron"]
    raw: str                          # "+3M 25d" | "25th of month after quarter" | "0 0 25 3 *"
    description: str                  # "25-го числа через 3 месяца после отчётного"

    def __post_init__(self):
        valid_types = ("offset", "expression", "cron")
        if self.rule_type not in valid_types:
            raise ValueError(f"DueRule type must be one of {valid_types}")
        if not self.raw:
            raise ValueError("DueRule raw must not be empty")

    def compute_deadline(self, period: str, calendar: ...) -> date:
        """Вычислить конкретную дату для заданного периода.

        period: "2026-Q1", "2026-06", "2025"
        """
        ...


# Парсер DueRule (вынесен отдельно для тестируемости)
class DueRuleParser(ABC):
    """Parse and compute deadlines from DueRule expressions."""

    @abstractmethod
    def parse(self, rule: DueRule) -> DueRuleAST:
        ...

    @abstractmethod
    def compute(self, ast: DueRuleAST, period_year: int,
                period_month: int | None, period_quarter: int | None) -> date:
        ...
```

### 2.5 Rule Evaluation Trace

```python
@dataclass(frozen=True)
class RuleEvaluationTrace:
    """Дерево трассировки вычисления RequirementExpression.

    Возвращается как часть результата оценки правила.
    Структура — рекурсивное дерево, соответствующее AST.

    Содержит идентификатор правила (rule_code, version_number) и
    effective_from для привязки к конкретной версии правила, которая
    была применена.
    """

    # ── Rule identity ──────────────────────────────────────────
    rule_code: RuleCode                # какое правило оценивалось
    version_number: int                # какая версия правила
    effective_from: date               # effective_from версии на момент оценки

    # ── Expression trace ───────────────────────────────────────
    expression_type: Literal["ALL", "ANY", "NOT", "FACT"]
    fact_code: str | None            # для FACT — какой бизнес-факт
    status: Literal["confirmed", "missing", "disputed", "skipped"]
    children: tuple["RuleEvaluationTrace", ...] = ()
    detail: str | None = None        # пояснение: "Факт revenue_posted подтверждён"

    # Пример:
    # ALL
    # ├── revenue_posted ✔    (confirmed)
    # ├── expenses ✔          (confirmed)
    # └── period_closed ✘     (missing)
    #     └── "Период 2026-06 ещё не закрыт"
```

### 2.6 Organization Override

```python
@dataclass(frozen=True)
class OverrideSource(str, Enum):
    """Источник переопределения с явной цепочкой приоритетов.

    Priority chain (высший → низший):
        LAW (0) → MANUAL (1) → IMPORT (2) → DEFAULT (3)

    Правило разрешения конфликтов:
    - При множественных override для одного organization_id + rule_code
      применяется override с наивысшим приоритетом (наименьший priority_number).
    - При равном приоритете — последняя версия с максимальным effective_from.
    - Если effective_from совпадает — ошибка конфигурации.
    """
    DEFAULT = "default"    # (3) системное значение (из Git)
    MANUAL = "manual"      # (1) ручное изменение пользователем
    IMPORT = "import"      # (2) импортировано из внешней системы
    LAW = "law"            # (0) изменение по закону (автоматическое обновление)

    @property
    def priority(self) -> int:
        """Числовой приоритет: 0 = высший, 3 = низший."""
        return _OVERRIDE_PRIORITY[self]


_OVERRIDE_PRIORITY: dict[OverrideSource, int] = {
    OverrideSource.LAW:     0,
    OverrideSource.MANUAL:  1,
    OverrideSource.IMPORT:  2,
    OverrideSource.DEFAULT: 3,
}


@dataclass(frozen=True)
class OrganizationOverride:
    """Переопределение правила для конкретной организации.

    Двухуровневая модель:
    - Default Rules (Git) — общесистемные, readonly
    - OrganizationOverride (DB) — специфические для организации

    OrganizationOverride может:
    - Переопределить requirement_expression (добавить/убрать требования)
    - Переопределить due_rule (изменить срок сдачи)
    - Добавить override с новым effective_period
    """

    override_id: UUID
    organization_id: UUID              # ссылка на OrganizationProfile
    rule_code: RuleCode                # какое правило переопределяется

    # ── Override contents ────────────────────────────────────────
    # Переопределяем только то, что нужно изменить
    # None = использовать значение Default Rule
    requirement_expression: RequirementExpression | None = None
    due_rule: DueRule | None = None
    applies_to: dict | None = None     # дополнительные фильтры применимости

    # ── Effective period of the override ─────────────────────────
    # Override действует в этот период (может частично перекрывать Default)
    effective_from: date
    effective_to: date | None = None

    # ── Provenance ───────────────────────────────────────────────
    source: OverrideSource = OverrideSource.MANUAL
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    reason: str = ""                   # причина переопределения

    # ── Optimistic lock ──────────────────────────────────────────
    version: int = 1
```

### 2.7 Rule Resolver

```python
@dataclass(frozen=True)
class ResolvedRule:
    """Правило, готовое к применению для конкретной организации.

    Resolver объединяет Default Rule + Organization Override.
    """

    rule_code: RuleCode
    rule_name: str
    rule_version: RuleVersion          # какая версия Default Rule применена
    override: OrganizationOverride | None = None  # если был override

    # ── Resolved content ─────────────────────────────────────────
    requirement_expression: RequirementExpression  # финальное выражение
    due_rule: DueRule                              # финальный срок

    # ── Metadata ─────────────────────────────────────────────────
    effective_from: date
    effective_to: date | None
    resolution_trace: list[str]        # "default: usn_declaration v3" / "override: org=... v2"


class IRulesResolver(ABC):
    """Resolver — определяет, какие правила применимы к организации.

    Вход: OrganizationProfile + дата
    Выход: список ResolvedRule (правила, готовые к применению)

    Правила поиска:
    1. Найти все Default Rules, где applies_to совпадает с профилем организации
    2. Для каждого Default Rule проверить, есть ли OrganizationOverride
    3. Если есть — применить override, создав ResolvedRule
    4. Если нет — использовать Default Rule как есть
    5. Отфильтровать по effective_from/effective_to
    """

    @abstractmethod
    async def resolve(
        self,
        organization_id: UUID,
        at_date: date | None = None,
    ) -> list[ResolvedRule]:
        ...
```

### 2.8 Validation Result

```python
@dataclass(frozen=True)
class ValidationResult:
    """Результат валидации Rules Catalog.

    Проверки выполняются при старте сервиса.
    Ошибки блокируют запуск.
    """

    passed: bool
    errors: tuple["ValidationError", ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationError:
    """Детали ошибки валидации."""

    code: str                          # "cycle_detected" | "missing_fact" | "overlap" | "invalid_due"
    rule_code: RuleCode
    version_number: int | None
    detail: str                        # понятное описание проблемы


class OverrideConflictError(Exception):
    """Конфликт переопределений: два override с одинаковым приоритетом
    и одинаковым effective_from для одного rule_code."""
    pass


class OverlappingVersionError(Exception):
    """Новая версия правила пересекается с существующей опубликованной версией
    того же rule_code."""
    pass


def periods_overlap(
    from_a: date, to_a: date | None,
    from_b: date, to_b: date | None,
) -> bool:
    """Проверяет пересечение двух полуинтервалов [from, to).

    None = бесконечность.
    Пересечение: not (a_end <= b_start OR b_end <= a_start).
    """
    # Если A начинается после (или на) конца B — нет пересечения
    if to_b is not None and from_a >= to_b:
        return False
    # Если B начинается после (или на) конца A — нет пересечения
    if to_a is not None and from_b >= to_a:
        return False
    return True
```

### Domain Boundaries

```
┌──────────────────────────────────────────────────────────────┐
│                    Rules Catalog (этот Stream)                │
│                                                              │
│  ЗНАЕТ:                                                       │
│    • OrganizationProfile (через IOrganizationProfileRepo)     │
│    • TaxRegime, EntityType — для определения применимости     │
│                                                              │
│  НЕ ЗНАЕТ о:                                                  │
│    • Document / PDF                                          │
│    • Deal                                                    │
│    • Accounting Entry                                        │
│    • Business Events (Stream 3)                              │
│    • Business Facts (Stream 4)                               │
│    • Eligibility Engine (Stream 5) — только определяет        │
│      eligibility rules, но не запускает проверку              │
│                                                              │
│  Downstream consumers:                                        │
│    • Eligibility Engine (Stream 5) — resolves applicable      │
│      eligibility rules                                       │
│    • Dependency Engine (Stream 6) — resolves ALL rules        │
│      for an organization                                     │
│    • Compliance Timeline (Stream 8) — resolves due rules     │
│                                                              │
│  Не зависит от:                                              │
│    • Stream 3 (Business Events)                              │
│    • Stream 4 (Business Facts Engine)                        │
│    • Stream 5+ (Eligibility, Dependency, ...)                │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Invariants

### Domain invariants

| # | Инвариант | Проверка | Нарушение |
|:-:|:----------|:---------|:----------|
| 1 | `rule_code` — уникальный, непустой, только `[a-zA-Z0-9_-]` | Domain constructor | InvalidRuleCodeError |
| 2 | `RuleVersion.version_number` — монотонно возрастает для одного `rule_code` | Application Service | VersionConflictError |
| 3 | `effective_from < effective_to` (если effective_to не None) | Domain constructor | InvalidEffectivePeriodError |
| 4 | После PUBLISHED — RuleVersion immutable; никакие поля не меняются | Domain model (frozen) | MutationError (нельзя) |
| 5 | `DRAFT` → `PUBLISHED` только; нельзя откатить PUBLISHED → DRAFT | Application Service | IllegalStateTransitionError |
| 6 | `DEPRECATED` → `ARCHIVED` разрешён; обратно — нет | Application Service | IllegalStateTransitionError |
| 7 | RequirementExpression: FACT-узлы обязаны иметь fact_code | Domain constructor | ValidationError |
| 8 | RequirementExpression: ALL/ANY/NOT обязаны иметь children | Domain constructor | ValidationError |
| 9 | RequirementExpression: NOT — ровно один child | Domain constructor | ValidationError |
| 10 | DueRule: rule_type — только из допустимых (offset/expression/cron) | Domain constructor | InvalidDueRuleError |
| 11 | OrganizationOverride: `organization_id` должен существовать в OrganizationProfile | Repository check | OrganizationNotFoundError |
| 12 | OrganizationOverride: один organization_id + rule_code + effective_from — уникальны | Repository constraint | DuplicateOverrideError |
| 13 | OrganizationOverride: effective_period не может пересекаться с другим Override того же rule + org | Validation (startup) | OverlapError |
| 14 | `version` — монотонно возрастает при каждом update Override | Application Service | OptimisticLockError |
| 15 | **Override Priority**: при множественных override для одного org+rule_code побеждает LAW > MANUAL > IMPORT > DEFAULT; при равном приоритете — max effective_from | RulesResolver._select_best_override | OverrideConflictError |
| 16 | **Deterministic Resolution**: `ResolvedRuleSet` детерминирован. Для одинаковых: organization profile, date/time, catalog version, overrides — Resolver возвращает идентичный упорядоченный результат | RulesResolver.resolve | (invariant enforced by sort) |
| 17 | **MAX_EXPRESSION_DEPTH**: глубина RequirementExpression AST не более 32 | RequirementExpression.__post_init__ | ValueError |

### System invariants (Rules Catalog Validation — startup)

| # | Инвариант | Механизм |
|:-:|:----------|:---------|
| 15 | Нет циклов в RequirementExpression (ALL → ALL → ALL → ...) — граф зависимостей фактов должен быть DAG | Startup validator: topological sort |
| 16 | Все FACT-узлы ссылаются на существующие Business Fact definitions | Startup validator: reference check |
| 17 | Нет перекрывающихся effective_from/effective_to для одного rule_code | Startup validator: interval tree |
| 18 | Все DueRule выражения корректно парсятся (offset/cron/expression) | Startup validator: parse check |
| 19 | OrganizationOverride не конфликтуют (один rule + org → один active override) | Startup validator |
| 20 | Default Rules не имеют пересекающихся effective_period для одного rule_code | Startup validator |

### Cross-stream invariants

| # | Инвариант | Механизм |
|:-:|:----------|:---------|
| 21 | Все reference на OrganizationProfile идут через `organization_id` | FK / domain type |
| 22 | ResolvedRule не содержит ссылок на Default Rule после разрешения | Domain design |

---

## 4. Package Structure

```yaml
backend/compliance/
├── __init__.py
│
├── domain/
│   ├── __init__.py
│   ├── models.py                    # ComplianceRule, RuleVersion, RuleCode
│   ├── enums.py                     # RuleType, RuleStatus, OverrideSource
│   ├── expressions.py               # RequirementExpression, DueRule
│   ├── trace.py                     # RuleEvaluationTrace
│   ├── override.py                  # OrganizationOverride
│   ├── validation.py                # ValidationResult, ValidationError
│   └── errors.py                    # Domain-specific exceptions
│
├── application/
│   ├── __init__.py
│   ├── interfaces.py                # IRuleRepository, IOverrideRepository,
│   │                                # IRulesResolver, IDueRuleParser, IRulesValidator
│   ├── resolver.py                  # RulesResolver — concrete implementation
│   ├── expression_validator.py      # ExpressionValidator — валидатор AST (для Stream 4, 5)
│   ├── validator.py                 # RulesCatalogValidator — startup validation
│   └── services.py                  # RuleCatalogService (manage rules + overrides)
│
├── infrastructure/
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── repository.py            # SQLAlchemy implementations
│   │   └── tables.py                # ORM models for rules + overrides
│   ├── yaml_catalog/
│   │   ├── __init__.py
│   │   ├── loader.py                # Load Default Rules from YAML/JSON
│   │   └── schema.py                # Pydantic models for YAML validation
│   └── due_rule/
│       ├── __init__.py
│       ├── parser.py                # DueRuleParser implementation
│       └── calendar.py              # Business calendar for deadline computation
│
├── api/
│   ├── __init__.py
│   ├── routes.py                    # FastAPI router
│   └── schemas.py                   # Pydantic request/response models
│
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── test_domain.py           # ComplianceRule, RuleVersion invariants
    │   ├── test_expressions.py      # RequirementExpression, DueRule
    │   ├── test_trace.py            # RuleEvaluationTrace
    │   ├── test_resolver.py         # RulesResolver logic
    │   └── test_validator.py        # RulesCatalogValidator
    ├── integration/
    │   ├── test_repository.py       # SQLAlchemy CRUD
    │   └── test_yaml_loader.py      # YAML Default Rules loading
    └── e2e/
        └── test_api.py              # API endpoints
```

### Dependency flow

```
domain/  →  application/interfaces.py
                ↓
        application/resolver.py     (зависит от interfaces)
        application/validator.py    (зависит от interfaces)
        application/services.py     (зависит от interfaces)
                ↓
        infrastructure/persistence/     (реализует interfaces)
        infrastructure/yaml_catalog/    (реализует Default Rule loading)
        infrastructure/due_rule/        (реализует DueRuleParser)
                ↓
        api/routes.py                   (зависит от application)
```

### Default Rules structure (Git-based)

```
backend/compliance/defaults/
├── __init__.py
├── rules/
│   ├── usn/
│   │   ├── usn_6.yaml                # УСН 6% rules
│   │   ├── usn_15.yaml               # УСН 15% rules
│   │   └── usn_declaration.yaml      # Декларация по УСН
│   ├── osno/
│   │   ├── profit_tax.yaml           # Налог на прибыль
│   │   ├── vat_return.yaml           # Декларация по НДС
│   │   └── property_tax.yaml         # Налог на имущество
│   ├── patent/
│   │   └── patent_cost.yaml          # Стоимость патента
│   └── common/
│       ├── insurance.yaml            # Страховые взносы
│       ├── 6_ndfl.yaml               # 6-НДФЛ
│       └── rsb.yaml                  # РСВ (единый отчёт)
├── business_facts/
│   └── registry.yaml                 # Реестр бизнес-фактов
└── index.yaml                        # Индекс всех Default Rules
```

---

## 5. Repository Interfaces

### IRuleRepository

```python
# backend/compliance/application/interfaces.py (дополнение)

from abc import ABC, abstractmethod
from uuid import UUID
from compliance.domain.models import ComplianceRule, RuleVersion, RuleCode


class IRuleRepository(ABC):
    """Repository for ComplianceRules + RuleVersions.

    Default Rules (from Git) и Organization Overrides (from DB) хранятся отдельно.
    Этот репозиторий управляет ТОЛЬКО Default Rules в БД (кэш/индекс правил из Git).
    """

    ### ── ComplianceRule CRUD ────────────────────────────────────

    @abstractmethod
    async def get_rule(self, rule_code: RuleCode) -> ComplianceRule | None:
        """Get rule by code."""
        ...

    @abstractmethod
    async def list_rules(
        self,
        rule_type: RuleType | None = None,
        tax_regime: TaxRegime | None = None,
        status: RuleStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ComplianceRule]:
        """List rules with optional filters."""
        ...

    @abstractmethod
    async def add_rule(self, rule: ComplianceRule) -> ComplianceRule:
        """Create a new rule."""
        ...

    @abstractmethod
    async def update_rule(self, rule: ComplianceRule) -> ComplianceRule:
        """Update rule metadata (NOT versions — versions are immutable)."""
        ...

    ### ── RuleVersion CRUD ───────────────────────────────────────

    @abstractmethod
    async def get_version(self, version_id: UUID) -> RuleVersion | None:
        """Get a specific version by ID."""
        ...

    @abstractmethod
    async def get_latest_version(self, rule_code: RuleCode) -> RuleVersion | None:
        """Get the latest (highest version_number) version."""
        ...

    @abstractmethod
    async def get_active_version(
        self,
        rule_code: RuleCode,
        at_date: date,
    ) -> RuleVersion | None:
        """Get the version active at a specific date."""
        ...

    @abstractmethod
    async def get_version_history(
        self,
        rule_code: RuleCode,
    ) -> list[RuleVersion]:
        """Get all versions for a rule, ordered by version_number desc."""
        ...

    @abstractmethod
    async def add_version(self, version: RuleVersion) -> RuleVersion:
        """Add a new version (called when publishing)."""
        ...

    ### ── Bulk operations (for startup loading from Git) ─────────

    @abstractmethod
    async def bulk_upsert_rules(
        self,
        rules: list[ComplianceRule],
        versions: list[RuleVersion],
    ) -> None:
        """Atomic upsert of Default Rules from Git (startup/deply)."""
        ...
```

### IOverrideRepository

```python
class IOverrideRepository(ABC):
    """Repository for OrganizationOverrides (DB-stored, per-org)."""

    @abstractmethod
    async def get_override(
        self,
        organization_id: UUID,
        rule_code: RuleCode,
    ) -> OrganizationOverride | None:
        """Get override for specific org + rule. Returns latest version."""
        ...

    @abstractmethod
    async def list_overrides(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OrganizationOverride]:
        """List all overrides for an organization."""
        ...

    @abstractmethod
    async def add_override(
        self,
        override: OrganizationOverride,
    ) -> OrganizationOverride:
        """Add a new override (or replace existing for same org+rule+period)."""
        ...

    @abstractmethod
    async def update_override(
        self,
        override: OrganizationOverride,
    ) -> OrganizationOverride:
        """Update override (version increment)."""
        ...

    @abstractmethod
    async def delete_override(
        self,
        override_id: UUID,
    ) -> None:
        """Soft-delete an override (set archived_at)."""
        ...

    @abstractmethod
    async def get_active_overrides(
        self,
        organization_id: UUID,
        at_date: date,
    ) -> list[OrganizationOverride]:
        """Get all overrides active at a specific date."""
        ...
```

### Other Interfaces

```python
class IRulesResolver(ABC):
    """Определяет, какие правила применимы к организации на дату."""

    @abstractmethod
    async def resolve(
        self,
        organization_id: UUID,
        at_date: date | None = None,
    ) -> list[ResolvedRule]:
        ...


class IRulesValidator(ABC):
    """Валидатор Rules Catalog при старте сервиса."""

    @abstractmethod
    async def validate(
        self,
        rules: list[ComplianceRule],
        versions: list[RuleVersion],
    ) -> ValidationResult:
        ...


class IDefaultRuleLoader(ABC):
    """Загрузчик Default Rules из YAML/JSON в Git."""

    @abstractmethod
    async def load_all(self) -> tuple[list[ComplianceRule], list[RuleVersion]]:
        """Load all default rules from the Git-based catalog."""
        ...


class IDueRuleParser(ABC):
    """Parse and compute deadlines from DueRule expressions."""

    @abstractmethod
    def parse(self, rule: DueRule) -> DueRuleAST:
        ...

    @abstractmethod
    def compute(
        self,
        ast: DueRuleAST,
        period_year: int,
        period_month: int | None = None,
        period_quarter: int | None = None,
    ) -> date:
        ...
```

### Design rationale

- **Two repositories** — `IRuleRepository` (Default Rules + versions) and `IOverrideRepository` (per-org overrides) are separate because they have different storage backends (Default → DB cache from Git, Override → DB-native)
- **IRulesResolver is a separate interface** — not part of any repository, because resolution logic (merge default + override) is non-trivial
- **IDefaultRuleLoader abstracts Git source** — allows switching from local YAML to S3/GitHub API without changing domain
- **IDueRuleParser is an interface** — enables testing with mock calendar, injecting different business calendars (Russian holidays vs regional)

---

## 6. Application Services

### Application Commands

```python
# backend/compliance/application/commands.py (дополнение)

from dataclasses import dataclass, field
from uuid import UUID
from compliance.domain.models import RuleCode, RuleType
from compliance.domain.enums import RuleStatus
from compliance.domain.expressions import RequirementExpression, DueRule
from compliance.domain.override import OverrideSource


## ── Rule Commands ─────────────────────────────────────────────

@dataclass
class CreateRuleCommand:
    rule_code: str
    rule_type: RuleType
    name: str
    description: str = ""
    category: str = ""
    tags: tuple[str, ...] = ()
    created_by: str = "system"


@dataclass
class PublishRuleVersionCommand:
    rule_code: str
    effective_from: date
    effective_to: date | None = None
    requirement_expression: RequirementExpression | None = None
    due_rule: DueRule | None = None
    applies_to_tax_regimes: frozenset[TaxRegime] = ...
    applies_to_entity_types: frozenset[EntityType] = ...
    applies_to_regions: frozenset[str] | None = None
    applies_to_has_employees: bool | None = None
    frequency: str = "yearly"
    source: str = "default"
    reference_law: str = ""
    change_reason: str = ""
    published_by: str = "system"


@dataclass
class DeprecateRuleCommand:
    rule_code: str
    updated_by: str


## ── Override Commands ─────────────────────────────────────────

@dataclass
class CreateOverrideCommand:
    organization_id: UUID
    rule_code: str
    requirement_expression: RequirementExpression | None = None
    due_rule: DueRule | None = None
    effective_from: date
    effective_to: date | None = None
    source: OverrideSource = OverrideSource.MANUAL
    created_by: str
    reason: str = ""


## ── Resolver Commands ─────────────────────────────────────────

@dataclass
class ResolveRulesQuery:
    """Query for RulesResolver: какие правила применимы к организации?"""
    organization_id: UUID
    at_date: date | None = None       # None = сегодня
```

### RuleCatalogService

```python
# backend/compliance/application/services.py (дополнение)


class RuleCatalogService:
    """Use cases for managing Rules Catalog and Organization Overrides."""

    def __init__(
        self,
        rule_repo: IRuleRepository,
        override_repo: IOverrideRepository,
        default_rule_loader: IDefaultRuleLoader,
        clock: Clock,
    ):
        self._rule_repo = rule_repo
        self._override_repo = override_repo
        self._loader = default_rule_loader
        self._clock = clock

    async def create_rule(self, data: CreateRuleCommand) -> ComplianceRule:
        """Create a new rule in DRAFT status."""
        now = self._clock.now()
        rule = ComplianceRule(
            rule_code=RuleCode(data.rule_code),
            rule_type=data.rule_type,
            name=data.name,
            description=data.description,
            category=data.category,
            tags=data.tags,
            status=RuleStatus.DRAFT,
            created_at=now,
            updated_at=now,
            created_by=data.created_by,
            updated_by=data.created_by,
        )
        return await self._rule_repo.add_rule(rule)

    async def publish_version(self, data: PublishRuleVersionCommand) -> tuple[ComplianceRule, RuleVersion]:
        """Publish a new immutable version of a rule.

        Атомарно проверяет:
        - Пересечение effective_period с существующими PUBLISHED версиями
          того же rule_code
        - В одной транзакции: check + insert
        """
        now = self._clock.now()
        rule = await self._rule_repo.get_or_raise(RuleCode(data.rule_code))
        latest = await self._rule_repo.get_latest_version(RuleCode(data.rule_code))

        # ── Runtime overlap check ──────────────────────────────
        # Загружаем все опубликованные версии для этого rule_code
        existing_versions = await self._rule_repo.get_version_history(RuleCode(data.rule_code))

        new_from = data.effective_from
        new_to = data.effective_to

        for existing in existing_versions:
            # Проверяем пересечение: [new_from, new_to) ∩ [existing.effective_from, existing.effective_to)
            if periods_overlap(new_from, new_to, existing.effective_from, existing.effective_to):
                raise OverlappingVersionError(
                    f"New version [{new_from}, {new_to}) overlaps with existing "
                    f"version {existing.version_number}: "
                    f"[{existing.effective_from}, {existing.effective_to}) "
                    f"for rule {data.rule_code}. "
                    f"Existing version_id: {existing.version_id}"
                )

        version = RuleVersion(
            version_id=uuid4(),
            rule_code=RuleCode(data.rule_code),
            version_number=(latest.version_number + 1) if latest else 1,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            requirement_expression=data.requirement_expression,
            due_rule=data.due_rule,
            applies_to_tax_regimes=data.applies_to_tax_regimes,
            applies_to_entity_types=data.applies_to_entity_types,
            applies_to_regions=data.applies_to_regions,
            applies_to_has_employees=data.applies_to_has_employees,
            frequency=data.frequency,
            source=data.source,
            reference_law=data.reference_law,
            change_reason=data.change_reason,
            published_at=now,
            published_by=data.published_by,
        )

        await self._rule_repo.add_version(version)

        # Update rule status to PUBLISHED
        updated_rule = rule.publish(
            published_by=data.published_by,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )
        updated_rule = await self._rule_repo.update_rule(updated_rule)
        return updated_rule, version

    async def create_override(self, data: CreateOverrideCommand) -> OrganizationOverride:
        """Create or replace an organization-specific override."""
        # Verify org exists
        org = await self._org_repo.get_or_raise(data.organization_id)  # injected separately

        now = self._clock.now()
        override = OrganizationOverride(
            override_id=uuid4(),
            organization_id=data.organization_id,
            rule_code=RuleCode(data.rule_code),
            requirement_expression=data.requirement_expression,
            due_rule=data.due_rule,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            source=data.source,
            created_at=now,
            updated_at=now,
            created_by=data.created_by,
            updated_by=data.updated_by,
            reason=data.reason,
            version=1,
        )
        return await self._override_repo.add_override(override)

    async def reload_defaults(self) -> ValidationResult:
        """Reload Default Rules from Git and re-validate.

        Вызывается:
        - При старте сервиса (автоматически)
        - При деплое новых правил (manual trigger)
        """
        rules, versions = await self._loader.load_all()
        validator = RulesCatalogValidator()
        result = validator.validate(rules, versions)

        if result.passed:
            await self._rule_repo.bulk_upsert_rules(rules, versions)

        return result
```

### RulesResolver (concrete implementation)

```python
# backend/compliance/application/resolver.py


class RulesResolver:
    """Resolves applicable rules for an organization at a point in time.

    Алгоритм:
    1. Получить OrganizationProfile (через IOrganizationProfileRepository)
    2. Получить все Default Rules, где applies_to совпадает с профилем
    3. Для каждого rule_code загрузить все OrganizationOverride, активные на дату
    4. Выбрать override по priority chain: LAW > MANUAL > IMPORT > DEFAULT
    5. При равном приоритете — максимальный effective_from
    6. При равном effective_from — ошибка конфигурации
    7. Применить выбранный Override (merge поверх Default)
    8. Отфильтровать по effective_from/effective_to относительно at_date
    9. Вернуть ResolvedRule[]

    Determinism гарантирован: для одинаковых входных данных
    (profile, date, catalog version, overrides) Resolver
    ВСЕГДА возвращает идентичный упорядоченный результат.
    """

    def __init__(
        self,
        org_repo: IOrganizationProfileRepository,
        rule_repo: IRuleRepository,
        override_repo: IOverrideRepository,
    ):
        self._org_repo = org_repo
        self._rule_repo = rule_repo
        self._override_repo = override_repo

    @staticmethod
    def _select_best_override(
        overrides: list[OrganizationOverride],
    ) -> OrganizationOverride | None:
        """Выбрать override по priority chain.

        Правила:
        1. LAW > MANUAL > IMPORT > DEFAULT
        2. При равном приоритете — максимальный effective_from
        3. При равном effective_from — ConflictError
        """
        if not overrides:
            return None

        # Sort by priority (ascending = higher priority first), then by effective_from desc
        sorted_ovs = sorted(
            overrides,
            key=lambda ov: (ov.source.priority, -ov.effective_from.toordinal()),
        )

        best = sorted_ovs[0]
        # Check for conflict: same priority AND same effective_from
        for ov in sorted_ovs[1:]:
            if ov.source.priority == best.source.priority and ov.effective_from == best.effective_from:
                raise OverrideConflictError(
                    f"Conflicting overrides for {best.rule_code}: "
                    f"both have source={best.source.value} priority={best.source.priority} "
                    f"and effective_from={best.effective_from}. "
                    f"Override IDs: {best.override_id}, {ov.override_id}"
                )

        return best

    async def resolve(
        self,
        organization_id: UUID,
        at_date: date | None = None,
    ) -> list[ResolvedRule]:
        at_date = at_date or date.today()

        # 1. Get org profile
        org = await self._org_repo.get_or_raise(organization_id)

        # 2. Find all rules applicable to this org
        #    (by tax_regime, entity_type, region, has_employees)
        candidate_rules = await self._rule_repo.find_applicable(
            tax_regime=org.tax_regime,
            entity_type=org.entity_type,
            region=org.region_code,
            has_employees=org.has_employees,
            at_date=at_date,
        )

        # 3. Get ALL active overrides for this org (not deduplicated by rule_code)
        raw_overrides = await self._override_repo.get_active_overrides(
            organization_id, at_date
        )
        # Group overrides by rule_code for priority-based selection
        override_groups: dict[RuleCode, list[OrganizationOverride]] = {}
        for ov in raw_overrides:
            override_groups.setdefault(ov.rule_code, []).append(ov)

        # 4. Resolve each rule with priority-based override selection
        resolved: list[ResolvedRule] = []
        for rule, version in candidate_rules:
            rule_overrides = override_groups.get(rule.rule_code, [])
            best_override = self._select_best_override(rule_overrides)

            trace = [f"default: {rule.rule_code} v{version.version_number}"]

            if best_override:
                trace.append(
                    f"override: org={organization_id} v{best_override.version} "
                    f"source={best_override.source.value} (priority={best_override.source.priority})"
                )

            resolved.append(ResolvedRule(
                rule_code=rule.rule_code,
                rule_name=rule.name,
                rule_version=version,
                override=best_override,
                requirement_expression=(
                    best_override.requirement_expression
                    if best_override and best_override.requirement_expression
                    else version.requirement_expression
                ),
                due_rule=(
                    best_override.due_rule
                    if best_override and best_override.due_rule
                    else version.due_rule
                ),
                effective_from=(
                    max(version.effective_from, best_override.effective_from)
                    if best_override
                    else version.effective_from
                ),
                effective_to=(
                    min(version.effective_to, best_override.effective_to)
                    if best_override and version.effective_to and best_override.effective_to
                    else (version.effective_to or best_override.effective_to if best_override else version.effective_to)
                ),
                resolution_trace=trace,
            ))

        # 5. Sort for determinism: by effective_from asc, then rule_code asc
        resolved.sort(key=lambda r: (r.effective_from, r.rule_code.code))
        return resolved
```

### ExpressionValidator (выделенный валидатор выражений)

```python
# backend/compliance/application/expression_validator.py

from compliance.domain.expressions import RequirementExpression
from compliance.domain.validation import ValidationError


class ExpressionValidator:
    """Валидатор RequirementExpression AST.

    Выделен в отдельный класс в application/ для независимого
    использования Stream 4 (Business Facts Engine) и Stream 5
    (Eligibility Engine).
    """

    def __init__(self, max_depth: int = 32):
        self._max_depth = max_depth

    def validate(
        self,
        expression: RequirementExpression,
        known_fact_codes: set[str] | None = None,
    ) -> list[ValidationError]:
        """Валидировать RequirementExpression.

        Проверки:
        1. MAX_EXPRESSION_DEPTH — глубина AST
        2. fact_code — ссылка на существующий Business Fact
           (если передан known_fact_codes)
        3. Структурные правила (type + children + fact_code согласованность)
        4. Отсутствие дублирующих fact_code в рамках одного ALL/ANY/NOT
        """
        errors: list[ValidationError] = []

        # Check 1: max depth (дополнительная к __post_init__)
        depth = self._compute_depth(expression)
        if depth > self._max_depth:
            errors.append(ValidationError(
                code="expression_too_deep",
                rule_code=RuleCode(""),
                version_number=None,
                detail=f"Expression depth {depth} exceeds max {self._max_depth}",
            ))

        # Check 2: fact reference validity
        if known_fact_codes is not None:
            missing = self._find_unknown_facts(expression, known_fact_codes)
            for fact in missing:
                errors.append(ValidationError(
                    code="missing_fact",
                    rule_code=RuleCode(""),
                    version_number=None,
                    detail=f"Business fact '{fact}' not found in registry",
                ))

        # Check 3: structural rules (в дополнение к __post_init__)
        structural_errors = self._check_structure(expression)
        errors.extend(structural_errors)

        return errors

    def _compute_depth(self, expr: RequirementExpression) -> int:
        if not expr.children:
            return 1
        return 1 + max(self._compute_depth(c) for c in expr.children)

    def _find_unknown_facts(
        self,
        expr: RequirementExpression,
        known_fact_codes: set[str],
    ) -> set[str]:
        if expr.expression_type == "FACT":
            if expr.fact_code and expr.fact_code not in known_fact_codes:
                return {expr.fact_code}
            return set()
        result: set[str] = set()
        for child in expr.children:
            result |= self._find_unknown_facts(child, known_fact_codes)
        return result

    def _check_structure(
        self,
        expr: RequirementExpression,
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []

        # No duplicate fact_codes within the same logical operator
        if expr.expression_type in ("ALL", "ANY"):
            fact_codes = [
                c.fact_code
                for c in expr.children
                if c.expression_type == "FACT"
            ]
            if len(fact_codes) != len(set(fact_codes)):
                errors.append(ValidationError(
                    code="duplicate_fact",
                    rule_code=RuleCode(""),
                    version_number=None,
                    detail=f"Duplicate fact_code in {expr.expression_type}: {fact_codes}",
                ))

        # Recursively check children
        for child in expr.children:
            errors.extend(self._check_structure(child))

        return errors
```

```python
# backend/compliance/application/validator.py


class RulesCatalogValidator:
    """Валидация Rules Catalog при старте сервиса.

    Проверки:
    - Циклы в RequirementExpression (DAG check)
    - Ссылки на существующие Business Facts
    - Перекрывающиеся effective_from/effective_to
    - Корректность DueRule
    - Конфликтующие OrganizationOverride
    """

    def validate(
        self,
        rules: list[ComplianceRule],
        versions: list[RuleVersion],
    ) -> ValidationResult:
        errors: list[ValidationError] = []
        warnings: list[str] = []

        # Check 1: Cycle detection in RequirementExpression DAG
        for v in versions:
            if self._has_cycles(v.requirement_expression):
                errors.append(ValidationError(
                    code="cycle_detected",
                    rule_code=v.rule_code,
                    version_number=v.version_number,
                    detail=f"Cycle detected in requirement expression: {v.requirement_expression}",
                ))

        # Check 2: Fact reference validation
        for v in versions:
            missing = self._find_missing_facts(v.requirement_expression)
            for fact in missing:
                errors.append(ValidationError(
                    code="missing_fact",
                    rule_code=v.rule_code,
                    version_number=v.version_number,
                    detail=f"Business fact '{fact}' not found in registry",
                ))

        # Check 3: Overlapping effective periods (same rule_code)
        for rule_code, rule_versions in self._group_by_rule(versions).items():
            overlaps = self._find_overlaps(rule_versions)
            for v1, v2 in overlaps:
                errors.append(ValidationError(
                    code="overlap",
                    rule_code=rule_code,
                    version_number=v1.version_number,
                    detail=f"Version {v1.version_number} overlaps with version "
                           f"{v2.version_number}: [{v1.effective_from}, {v1.effective_to}] "
                           f"∩ [{v2.effective_from}, {v2.effective_to}]",
                ))

        # Check 4: DueRule parsing
        for v in versions:
            try:
                parse_due_rule(v.due_rule)
            except DueRuleParseError as e:
                errors.append(ValidationError(
                    code="invalid_due",
                    rule_code=v.rule_code,
                    version_number=v.version_number,
                    detail=str(e),
                ))

        result = ValidationResult(
            passed=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
        return result
```

### Request/Response DTOs (API layer)

```python
# backend/compliance/api/schemas.py

from pydantic import BaseModel, Field


class RuleResponse(BaseModel):
    rule_code: str
    rule_type: str
    name: str
    description: str
    status: str
    current_version: RuleVersionResponse | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str


class RuleVersionResponse(BaseModel):
    version_number: int
    effective_from: date
    effective_to: date | None
    requirement_expression: dict  # serialized AST
    due_rule: dict                 # serialized DueRule
    frequency: str
    source: str
    reference_law: str
    published_at: datetime


class OverrideRequest(BaseModel):
    organization_id: UUID
    rule_code: str
    requirement_expression: dict | None = None
    due_rule: dict | None = None
    effective_from: date
    effective_to: date | None = None
    source: str = "manual"
    reason: str = ""


class OverrideResponse(BaseModel):
    override_id: UUID
    organization_id: UUID
    rule_code: str
    effective_from: date
    effective_to: date | None
    source: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    version: int


class ResolveRulesResponse(BaseModel):
    organization_id: UUID
    at_date: date
    rules: list[ResolvedRuleResponse]


class ResolvedRuleResponse(BaseModel):
    rule_code: str
    rule_name: str
    requirement_expression: dict
    due_rule: dict
    effective_from: date
    effective_to: date | None
    resolution_trace: list[str]
```

---

## 7. Persistence Model

### Table: `compliance.rules`

```sql
CREATE TABLE compliance.rules (
    rule_code           VARCHAR(100)    NOT NULL,
    rule_type           VARCHAR(20)     NOT NULL CHECK (rule_type IN (
                            'tax', 'reporting', 'eligibility', 'due'
                        )),
    name                VARCHAR(500)    NOT NULL,
    description         TEXT            NOT NULL DEFAULT '',
    category            VARCHAR(100)    NOT NULL DEFAULT '',
    tags                TEXT[]          NOT NULL DEFAULT '{}',
    status              VARCHAR(20)     NOT NULL DEFAULT 'draft' CHECK (status IN (
                            'draft', 'published', 'deprecated', 'archived'
                        )),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_by          VARCHAR(100)    NOT NULL,
    updated_by          VARCHAR(100)    NOT NULL,

    CONSTRAINT pk_rules PRIMARY KEY (rule_code)
);

CREATE INDEX idx_rules_type ON compliance.rules (rule_type);
CREATE INDEX idx_rules_status ON compliance.rules (status);
```

### Table: `compliance.rule_versions`

```sql
CREATE TABLE compliance.rule_versions (
    version_id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    rule_code               VARCHAR(100)    NOT NULL REFERENCES compliance.rules(rule_code),
    version_number          INTEGER         NOT NULL,

    -- Effective period
    effective_from          DATE            NOT NULL,
    effective_to            DATE,           -- NULL = бессрочно

    -- Rule content (stored as JSONB for flexibility)
    requirement_expression  JSONB           NOT NULL,  -- AST: {type, fact_code, children, criticality, notes}
    due_rule                JSONB           NOT NULL,  -- {rule_type, raw, description}

    -- Applicability filters
    applies_to_tax_regimes  TEXT[]          NOT NULL,
    applies_to_entity_types TEXT[]          NOT NULL,
    applies_to_regions      TEXT[],                     -- NULL = все регионы
    applies_to_has_employees BOOLEAN,                   -- NULL = не важно

    -- Metadata
    frequency               VARCHAR(20)     NOT NULL DEFAULT 'yearly',
    source                  VARCHAR(20)     NOT NULL DEFAULT 'default' CHECK (source IN (
                                'default', 'manual', 'import', 'law'
                            )),
    reference_law           TEXT            NOT NULL DEFAULT '',
    change_reason           TEXT            NOT NULL DEFAULT '',

    -- Audit: immutable version
    published_at            TIMESTAMPTZ     NOT NULL DEFAULT now(),
    published_by            VARCHAR(100)    NOT NULL,

    CONSTRAINT pk_rule_versions PRIMARY KEY (version_id),
    CONSTRAINT uq_rule_versions_rule_version UNIQUE (rule_code, version_number),
    CONSTRAINT fk_rule_versions_rule FOREIGN KEY (rule_code)
        REFERENCES compliance.rules(rule_code)
);

CREATE INDEX idx_rule_versions_code ON compliance.rule_versions (rule_code);
CREATE INDEX idx_rule_versions_active ON compliance.rule_versions (rule_code, effective_from, effective_to);
```

### Table: `compliance.organization_overrides`

```sql
CREATE TABLE compliance.organization_overrides (
    override_id             UUID            NOT NULL DEFAULT gen_random_uuid(),
    organization_id         UUID            NOT NULL REFERENCES compliance.organization_profiles(organization_id),
    rule_code               VARCHAR(100)    NOT NULL REFERENCES compliance.rules(rule_code),  -- FK: защита ссылочной целостности

    -- Override content (NULL = use default)
    requirement_expression  JSONB,           -- NULL = использовать default
    due_rule                JSONB,           -- NULL = использовать default
    applies_to_overrides    JSONB,           -- дополнительные фильтры (опционально)

    -- Effective period of the override
    effective_from          DATE            NOT NULL,
    effective_to            DATE,           -- NULL = бессрочно

    -- Provenance
    source                  VARCHAR(20)     NOT NULL DEFAULT 'manual' CHECK (source IN (
                                'default', 'manual', 'import', 'law'
                            )),
    reason                  TEXT            NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_by              VARCHAR(100)    NOT NULL,
    updated_by              VARCHAR(100)    NOT NULL,
    version                 INTEGER         NOT NULL DEFAULT 1,
    archived_at             TIMESTAMPTZ,             -- soft-delete

    CONSTRAINT pk_organization_overrides PRIMARY KEY (override_id),
    CONSTRAINT uq_org_override UNIQUE (organization_id, rule_code, effective_from)
);

CREATE INDEX idx_overrides_org ON compliance.organization_overrides (organization_id);
CREATE INDEX idx_overrides_active ON compliance.organization_overrides (organization_id, effective_from, effective_to);
CREATE INDEX idx_overrides_rule_code ON compliance.organization_overrides (rule_code);
CREATE INDEX idx_rule_versions_period ON compliance.rule_versions (effective_from, effective_to);
-- Optional: GIN index for JSONB queries on requirement_expression
-- CREATE INDEX idx_rule_versions_expr_gin ON compliance.rule_versions USING GIN (requirement_expression);
```

### Default Rules YAML Format (example)

```yaml
# backend/compliance/defaults/rules/usn/usn_declaration.yaml

rule_code: "usn_declaration"
rule_type: "reporting"
name: "Декларация по УСН"
description: "Налоговая декларация по налогу, уплачиваемому в связи с применением УСН"

versions:
  - version_number: 3
    effective_from: "2026-01-01"
    effective_to: null
    requirement_expression:
      type: "ALL"
      children:
        - type: "FACT"
          fact_code: "revenue_posted"
          criticality: "critical"
        - type: "FACT"
          fact_code: "expenses_confirmed"
          criticality: "required"
        - type: "FACT"
          fact_code: "period_closed"
          criticality: "critical"
    due_rule:
      rule_type: "offset"
      raw: "+3M 25d"
      description: "25-го числа через 3 месяца после отчётного периода"
    applies_to:
      tax_regimes: ["usn_6", "usn_15"]
      entity_types: ["ip", "ooo"]
    frequency: "yearly"
    reference_law: "НК РФ ст.346.23"
```

### ORM Mapping (SQLAlchemy)

```python
# backend/compliance/infrastructure/persistence/tables.py

class RuleTable(Base):
    __tablename__ = "rules"
    __table_args__ = {"schema": "compliance"}

    rule_code: Mapped[str] = mapped_column(String(100), primary_key=True)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=[])
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    created_by: Mapped[str] = mapped_column(String(100))
    updated_by: Mapped[str] = mapped_column(String(100))


class RuleVersionTable(Base):
    __tablename__ = "rule_versions"
    __table_args__ = {"schema": "compliance"}

    version_id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    rule_code: Mapped[str] = mapped_column(String(100), ForeignKey("compliance.rules.rule_code"))
    version_number: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    requirement_expression: Mapped[dict] = mapped_column(JSONB)
    due_rule: Mapped[dict] = mapped_column(JSONB)
    applies_to_tax_regimes: Mapped[list[str]] = mapped_column(ARRAY(String))
    applies_to_entity_types: Mapped[list[str]] = mapped_column(ARRAY(String))
    applies_to_regions: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    applies_to_has_employees: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), default="yearly")
    source: Mapped[str] = mapped_column(String(20), default="default")
    reference_law: Mapped[str] = mapped_column(Text, default="")
    change_reason: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    published_by: Mapped[str] = mapped_column(String(100))


class OrganizationOverrideTable(Base):
    __tablename__ = "organization_overrides"
    __table_args__ = {"schema": "compliance"}

    override_id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(SA_UUID, ForeignKey("compliance.organization_profiles.organization_id"))
    rule_code: Mapped[str] = mapped_column(String(100), ForeignKey("compliance.rules.rule_code"))  # FK integrity
    requirement_expression: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    due_rule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    applies_to_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    created_by: Mapped[str] = mapped_column(String(100))
    updated_by: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

---

## 8. API Contract

### Endpoints

```yaml
Rules:
  GET    /api/v1/rules                                          → ListRulesResponse
  POST   /api/v1/rules                                          → RuleResponse (create draft)
  GET    /api/v1/rules/{rule_code}                              → RuleResponse
  PUT    /api/v1/rules/{rule_code}                              → RuleResponse (update metadata)
  POST   /api/v1/rules/{rule_code}/publish                      → RuleVersionResponse
  POST   /api/v1/rules/{rule_code}/deprecate                    → RuleResponse
  GET    /api/v1/rules/{rule_code}/versions                     → list[RuleVersionResponse]
  GET    /api/v1/rules/{rule_code}/versions/active?at_date=...  → RuleVersionResponse

Overrides:
  GET    /api/v1/organizations/{organization_id}/overrides      → list[OverrideResponse]
  POST   /api/v1/organizations/{organization_id}/overrides      → OverrideResponse
  PUT    /api/v1/organizations/{organization_id}/overrides/{id} → OverrideResponse
  DELETE /api/v1/organizations/{organization_id}/overrides/{id} → 204 (soft-delete)

Resolver:
  GET    /api/v1/organizations/{organization_id}/applicable-rules?at_date=...  → ResolveRulesResponse

Admin:
  POST   /api/v1/admin/rules/reload                              → ValidationResult (reload from Git)
```

### Request/Response Examples

```json
// POST /api/v1/rules
// Request:
{
  "rule_code": "usn_declaration",
  "rule_type": "reporting",
  "name": "Декларация по УСН",
  "description": "Налоговая декларация по УСН",
  "category": "tax",
  "tags": ["yearly", "federal", "simplified"],
  "created_by": "admin"
}

// Response (201):
{
  "rule_code": "usn_declaration",
  "rule_type": "reporting",
  "name": "Декларация по УСН",
  "status": "draft",
  "created_at": "2026-07-23T10:00:00Z",
  "created_by": "admin"
}
```

```json
// POST /api/v1/rules/usn_declaration/publish
// Request:
{
  "effective_from": "2026-01-01",
  "effective_to": null,
  "requirement_expression": {
    "type": "ALL",
    "children": [
      {"type": "FACT", "fact_code": "revenue_posted", "criticality": "critical"},
      {"type": "FACT", "fact_code": "expenses_confirmed", "criticality": "required"},
      {"type": "FACT", "fact_code": "period_closed", "criticality": "critical"}
    ]
  },
  "due_rule": {
    "rule_type": "offset",
    "raw": "+3M 25d",
    "description": "25-го числа через 3 месяца"
  },
  "applies_to_tax_regimes": ["usn_6", "usn_15"],
  "applies_to_entity_types": ["ip", "ooo"],
  "frequency": "yearly",
  "reference_law": "НК РФ ст.346.23",
  "published_by": "admin"
}

// Response (201):
{
  "version_id": "b2c3d4e5-...",
  "rule_code": "usn_declaration",
  "version_number": 1,
  "effective_from": "2026-01-01",
  "effective_to": null,
  "requirement_expression": { ... },
  "due_rule": { ... },
  "frequency": "yearly",
  "published_at": "2026-07-23T10:00:00Z",
  "published_by": "admin"
}
```

```json
// POST /api/v1/organizations/{org_id}/overrides
// Request:
{
  "rule_code": "usn_declaration",
  "effective_from": "2026-07-01",
  "effective_to": null,
  "due_rule": {
    "rule_type": "offset",
    "raw": "+3M 20d",
    "description": "20-го числа через 3 месяца"
  },
  "source": "manual",
  "reason": "Региональный УФНС установил срок до 20-го числа",
  "created_by": "accountant@example.com"
}

// Response (201):
{
  "override_id": "c3d4e5f6-...",
  "organization_id": "a1b2c3d4-...",
  "rule_code": "usn_declaration",
  "due_rule": { ... },
  "effective_from": "2026-07-01",
  "source": "manual",
  "created_at": "2026-07-23T10:00:00Z",
  "created_by": "accountant@example.com",
  "version": 1
}
```

```json
// GET /api/v1/organizations/{org_id}/applicable-rules?at_date=2026-07-23
// Response (200):
{
  "organization_id": "a1b2c3d4-...",
  "at_date": "2026-07-23",
  "rules": [
    {
      "rule_code": "usn_declaration",
      "rule_name": "Декларация по УСН",
      "requirement_expression": {
        "type": "ALL",
        "children": [
          {"type": "FACT", "fact_code": "revenue_posted", "criticality": "critical"},
          {"type": "FACT", "fact_code": "expenses_confirmed", "criticality": "required"},
          {"type": "FACT", "fact_code": "period_closed", "criticality": "critical"}
        ]
      },
      "due_rule": {
        "rule_type": "offset",
        "raw": "+3M 20d",
        "description": "20-го числа через 3 месяца"
      },
      "effective_from": "2026-07-01",
      "effective_to": null,
      "resolution_trace": [
        "default: usn_declaration v1",
        "override: org=a1b2c3d4 v1"
      ]
    }
  ]
}
```

### Error responses

```json
// 404 Rule Not Found
{"detail": "Rule not found", "code": "rule_not_found", "rule_code": "usn_declaration"}

// 409 Version Conflict (override overlap)
{"detail": "Override period overlaps with existing override", "code": "override_overlap",
 "existing": {"override_id": "c3d4e5f6-...", "effective_from": "2026-01-01", "effective_to": "2026-06-30"}}

// 422 Validation Error (startup)
{"detail": "Rules catalog validation failed", "code": "validation_failed",
 "errors": [{"code": "cycle_detected", "rule_code": "usn_declaration", "detail": "..."}]}
```

---

## 9. Sequence Diagrams

### 9.1 Publish a New Rule Version

```
Admin                   API Router            RuleCatalogService       RuleRepo          Database
  │                        │                        │                    │                  │
  │  POST /rules/{code}    │                        │                    │                  │
  │  /publish              │                        │                    │                  │
  │───────────────────────▶│                        │                    │                  │
  │                        │  PublishVersionCmd     │                    │                  │
  │                        │───────────────────────▶│                    │                  │
  │                        │                        │                    │                  │
  │                        │                        │  get_or_raise()    │                  │
  │                        │                        │───────────────────▶│─── SELECT ──────▶│
  │                        │                        │◀── Rule ──────────│◀── Row ──────────│
  │                        │                        │                    │                  │
  │                        │                        │  get_latest_ver()  │                  │
  │                        │                        │───────────────────▶│─── SELECT ──────▶│
  │                        │                        │◀── Latest │None ──│◀── Row │None ────│
  │                        │                        │                    │                  │
  │                        │                        │  Build RuleVersion │                  │
  │                        │                        │  (frozen, UUID)    │                  │
  │                        │                        │  version_number++  │                  │
  │                        │                        │                    │                  │
  │                        │                        │  add_version(ver)  │                  │
  │                        │                        │───────────────────▶│─── INSERT ──────▶│
  │                        │                        │◀── version ───────│◀── OK ───────────│
  │                        │                        │                    │                  │
  │                        │                        │  update_rule() →   │                  │
  │                        │                        │  PUBLISHED         │                  │
  │                        │                        │───────────────────▶│─── UPDATE ──────▶│
  │                        │                        │◀── rule ──────────│◀── OK ───────────│
  │                        │                        │                    │                  │
  │                        │  RuleVersionResponse   │                    │                  │
  │                        │◀───────────────────────│                    │                  │
  │◀─── 201 Created ───────│                        │                    │                  │
```

### 9.2 Resolve Applicable Rules for Organization

```
Dependency Engine        RulesResolver         OrgRepo      RuleRepo     OverrideRepo     DB
      │                      │                   │            │              │             │
      │  resolve(org_id)     │                   │            │              │             │
      │─────────────────────▶│                   │            │              │             │
      │                      │                   │            │              │             │
      │                      │  get_or_raise()   │            │              │             │
      │                      │──────────────────▶│            │              │             │
      │                      │◀── Profile ──────│            │              │             │
      │                      │                   │            │              │             │
      │                      │  find_applicable  │            │              │             │
      │                      │  (tax_regime,     │───────────▶│              │             │
      │                      │   entity_type...) │            │─── SELECT ──▶│             │
      │                      │◀── [(Rule,Ver)] ─│◀───────────│              │             │
      │                      │                   │            │              │             │
      │                      │  get_active_ovs   │            │              │             │
      │                      │  (org_id, date)   │───────────▶│─────────────▶│─── SELECT ─▶│
      │                      │◀── [Override] ───│◀───────────│◀─────────────│◀── Rows ────│
      │                      │                   │            │              │             │
      │                      │  Merge Default + Override      │              │             │
      │                      │  → ResolvedRule[]             │              │             │
      │                      │                   │            │              │             │
      │◀── ResolvedRule[] ──│                   │            │              │             │
```

### 9.3 Startup Validation

```
Service Start           RulesCatalogValidator    DefaultRuleLoader     RuleRepo     DB
      │                        │                      │                  │           │
      │  reload_defaults()     │                      │                  │           │
      │───────────────────────▶│                      │                  │           │
      │                        │  load_all()          │                  │           │
      │                        │─────────────────────▶│                  │           │
      │                        │◀── [Rule, Version] ─│                  │           │
      │                        │                      │                  │           │
      │                        │  validate()          │                  │           │
      │                        │  ─ Check cycles      │                  │           │
      │                        │  ─ Check facts       │                  │           │
      │                        │  ─ Check overlaps    │                  │           │
      │                        │  ─ Check DueRules    │                  │           │
      │                        │                      │                  │           │
      │                        │  IF NOT passed:      │                  │           │
      │                        │  ─ RAISE error       │                  │           │
      │                        │  ─ Block startup     │                  │           │
      │                        │                      │                  │           │
      │                        │  IF passed:          │                  │           │
      │                        │  bulk_upsert_rules() │                  │           │
      │                        │──────────────────────▶─────────────────▶─── UPSERT─▶│
      │                        │                      │                  │           │
      │◀── ValidationResult ──│                      │                  │           │
```

### 9.4 Rule Evaluation Trace

```
Dependency Engine        RulesResolver        RuleEvaluator       BusinessFacts
      │                      │                     │                   │
      │  evaluate(org,       │                     │                   │
      │   rule_code, date)   │                     │                   │
      │─────────────────────▶│                     │                   │
      │                      │                     │                   │
      │                      │  resolve(org, date) │                   │
      │                      │── ResolvedRule ────▶│                   │
      │                      │                     │                   │
      │                      │                     │  For each FACT:   │
      │                      │                     │  check(fact_code)  │
      │                      │                     │──────────────────▶│
      │                      │                     │◀── status ───────│
      │                      │                     │                   │
      │                      │                     │  Build Trace Tree │
      │                      │                     │  ALL              │
      │                      │                     │  ├── rev_posted ✔│
      │                      │                     │  ├── expenses ✔  │
      │                      │                     │  └── period_cl'd ✘│
      │                      │                     │                   │
      │                      │◀── Trace ──────────│                   │
      │◀── RuleResult ──────│                     │                   │
      │  (status + trace)   │                     │                   │
```

---

## 10. Migration Plan

### Текущее состояние

Правил как сущности не существует. `TaxRegime` — просто enum в `OrganizationProfile`.
Нет:
- `compliance.rules` таблицы
- `compliance.rule_versions` таблицы
- `compliance.organization_overrides` таблицы
- YAML-каталога Default Rules

### Фаза 1 — создаём Rules Catalog (этот Stream)

1. Создаём три таблицы: `compliance.rules`, `compliance.rule_versions`, `compliance.organization_overrides`
2. Создаём YAML-каталог Default Rules в `backend/compliance/defaults/rules/`
3. Создаём `index.yaml` и `registry.yaml` (реестр бизнес-фактов)
4. Первый старт: загрузка Default Rules из YAML → БД → валидация → OK
5. API для управления правилами и Override'ами готов

### Фаза 2 — наполнение Default Rules (в рамках Stream 2)

1. Описать минимум 10 типовых правил для основных режимов:
   - УСН 6%: декларация, КУДиР, страховые взносы
   - УСН 15%: декларация, КУДиР, минимальный налог
   - ОСНО: НДС, налог на прибыль, налог на имущество
   - Патент: стоимость патента, отчётность
2. Каждое правило: `requirement_expression`, `due_rule`, `applies_to`, `effective_period`

### Фаза 3 — интеграция (после Stream 2)

1. **Stream 5 (Eligibility Engine)** читает eligibility rules через `IRulesResolver`
2. **Stream 6 (Dependency Engine)** читает всё через `IRulesResolver`
3. **Stream 4 (Business Facts Engine)** использует `fact_code` из RequirementExpression
4. **Stream 8 (Compliance Timeline)** использует `due_rule` для вычисления дедлайнов

### Стратегия совместимости

| Существующее | Новое | Совместимость |
|:-------------|:------|:--------------|
| `TaxRegime` enum (Stream 1) | `applies_to_tax_regimes` в RuleVersion | Полная — RuleVersion ссылается на TaxRegime |
| `reporting_period` в OrganizationProfile | `frequency` в RuleVersion | Дублирование; после Stream 2 `reporting_period` может быть deprecated |
| `EntityType` (Stream 1) | `applies_to_entity_types` в RuleVersion | Полная — Reference |

### Проблема: reporting_period

В Stream 1 `reporting_period` был помечен как архитектурный риск.
Stream 2 вводит `frequency` на уровне RuleVersion.
**Решение:** пока оставляем `reporting_period` в OrganizationProfile (для обратной совместимости со Stream 1),
но в Stream 2 добавляем `frequency` на уровне правила. После Stream 6 принимаем ADR: уничтожить
`reporting_period` или оставить.

---

## 11. Testing Strategy

### Unit tests (domain/)

| Тест | Что проверяет |
|:-----|:--------------|
| `test_create_rule` | ComplianceRule с валидными полями |
| `test_invalid_rule_code` | RuleCode — только допустимые символы |
| `test_rule_lifecycle_transitions` | DRAFT → PUBLISHED → DEPRECATED → ARCHIVED |
| `test_published_rule_immutable` | После PUBLISHED RuleVersion не меняется |
| `test_invalid_transition` | PUBLISHED → DRAFT запрещён |
| `test_requirement_expression_fact` | FACT — обязательный fact_code |
| `test_requirement_expression_all_any` | ALL/ANY — минимум один child |
| `test_requirement_expression_not` | NOT — ровно один child |
| `test_requirement_expression_nested` | Вложенные ALL(ANY(...), ANY(...)) |
| `test_due_rule_creation` | Offset, expression, cron |
| `test_due_rule_invalid_type` | Неверный rule_type |
| `test_organization_override` | Override с минимальными полями |
| `test_rule_evaluation_trace` | Структура дерева трассировки |
| `test_validation_error` | ValidationResult, ValidationError |
| `test_effective_period_invariant` | effective_from < effective_to |

### Unit tests (application/)

| Тест | Что проверяет |
|:-----|:--------------|
| `test_create_rule_success` | Полный цикл создания DRAFT |
| `test_publish_version` | Создание RuleVersion + обновление статуса |
| `test_publish_increments_version` | version_number монотонный |
| `test_resolver_no_overrides` | Default Rules только |
| `test_resolver_with_overrides` | Default + Override merge |
| `test_resolver_override_priority_law_wins` | LAW override побеждает MANUAL для того же rule_code |
| `test_resolver_override_priority_same_source_latest` | При равном приоритете — последний effective_from |
| `test_resolver_override_priority_conflict` | OverrideConflictError при одинаковом приоритете и effective_from |
| `test_resolver_deterministic_output` | Два resolve() с одинаковыми данными → идентичный порядок |
| `test_resolver_override_due_only` | Override только due, requirement — default |
| `test_resolver_effective_period` | Фильтрация по at_date |
| `test_resolver_no_rules` | Организация без подходящих правил |
| `test_create_override` | Создание Override |
| `test_override_overlap_detected` | Перекрывающиеся Override (в сервисе) |
| `test_validator_cycle_detection` | ALL → ALL → ALL — найдено |
| `test_validator_missing_fact` | FACT ссылается на несуществующий факт |
| `test_validator_overlap` | Перекрывающиеся effective_period |
| `test_validator_invalid_due` | Непарсящийся DueRule |
| `test_reload_defaults` | Загрузка из YAML + валидация |
| `test_publish_version_overlap_detected` | OverlappingVersionError при перекрытии effective_period |
| `test_publish_version_no_overlap` | Новая версия с неперекрывающимся периодом успешна |
| `test_expression_depth_limit` | ALL глубиной 33 — ошибка в __post_init__ |
| `test_expression_validator_standalone` | ExpressionValidator.validate() работает независимо от RulesCatalogValidator |
| `test_expression_validator_duplicate_facts` | Дублирующиеся fact_code в ALL/ANY — найдено |
| `test_expression_validator_known_facts` | Проверка known_fact_codes через ExpressionValidator |
| `test_rule_evaluation_trace_with_identity` | RuleEvaluationTrace содержит rule_code, version_number, effective_from |

### Integration tests (infrastructure/)

| Тест | Что проверяет |
|:-----|:--------------|
| `test_repository_rule_crud` | SQLAlchemy CRUD для правил |
| `test_repository_version_crud` | SQLAlchemy CRUD для версий |
| `test_repository_version_history` | Получение истории версий |
| `test_repository_active_version` | Получение версии по дате |
| `test_repository_override_crud` | SQLAlchemy CRUD для Override |
| `test_repository_override_unique` | Unique constraint overrides |
| `test_yaml_loader_load_all` | Загрузка всех YAML из defaults/ |
| `test_yaml_loader_invalid_yaml` | Ошибка при невалидном YAML |
| `test_yaml_loader_missing_fields` | Ошибка при неполном YAML |
| `test_due_parser_offset` | Парсинг "+3M 25d" |
| `test_due_parser_cron` | Парсинг "0 0 25 3 *" |

### API tests (e2e)

| Тест | Что проверяет |
|:-----|:--------------|
| `test_create_rule_endpoint` | POST /rules → 201 |
| `test_get_rule_endpoint` | GET /rules/{code} → 200 |
| `test_get_rule_404` | GET /rules/nonexistent → 404 |
| `test_publish_version_endpoint` | POST /rules/{code}/publish → 201 |
| `test_create_override_endpoint` | POST /organizations/{id}/overrides → 201 |
| `test_resolve_rules_endpoint` | GET /organizations/{id}/applicable-rules → 200 |
| `test_resolve_rules_with_overrides` | Override влияет на результат resolve |
| `test_reload_defaults_endpoint` | POST /admin/rules/reload → 200 |

### Contract test (Rules Resolver)

```python
# Abstract test for any IRulesResolver implementation
class RulesResolverContractTests(ABC):

    @abstractmethod
    def create_resolver(self) -> IRulesResolver:
        ...

    async def test_resolve_returns_applicable_rules(self):
        resolver = self.create_resolver()
        rules = await resolver.resolve(
            organization_id=UUID("..."), at_date=date(2026, 7, 23)
        )
        assert len(rules) > 0
        assert all(r.rule_code for r in rules)
        assert all(r.requirement_expression for r in rules)

    async def test_resolve_no_rules_for_unsupported_regime(self):
        resolver = self.create_resolver()
        rules = await resolver.resolve(
            organization_id=UUID("..."),  # e.g., PATENT regime
            at_date=date(2026, 7, 23),
        )
        # Only PATENT rules should be returned
        assert all(r.rule_code for r in rules)
```

---

## 12. Definition of Done

### Must have (критично для перехода к Stream 3)

- [ ] **Domain model** — `ComplianceRule`, `RuleVersion`, `RuleCode`, `RuleType`, `RuleStatus`
- [ ] **RequirementExpression** — AST с ALL/ANY/NOT/FACT, рекурсивная структура, валидация
- [ ] **DueRule** — DSL с rule_type (offset/expression/cron), парсер, compute_deadline
- [ ] **OrganizationOverride** — двухуровневая модель: Default (Git) + Override (DB)
- [ ] **Rule Evaluation Trace** — дерево трассировки, возвращаемое с каждым результатом
- [ ] **Rule Resolver** — `RulesResolver` с алгоритмом: Profile → Default Rules → Override → ResolvedRule
- [ ] **Repository interfaces** — `IRuleRepository`, `IOverrideRepository` в `application/interfaces.py`
- [ ] **SQLAlchemy implementations** — три таблицы: `rules`, `rule_versions`, `organization_overrides`
- [ ] **Default Rules YAML** — каталог в `backend/compliance/defaults/rules/` + загрузчик
- [ ] **Rules Catalog Validation** — при старте: циклы, ссылки, overlaps, DueRule parsing
- [ ] **API endpoints** — CRUD rules + versions, CRUD overrides, applicable-rules resolve, reload
- [ ] **DI wiring** — FastAPI DI для RuleCatalogService, RulesResolver
- [ ] **Unit tests** — domain model, expressions, resolver, validator (25+ тестов)
- [ ] **Override Priority Chain** — LAW > MANUAL > IMPORT > DEFAULT реализован в RulesResolver
- [ ] **Runtime overlap validation** — publish_version() проверяет пересечение effective_period
- [ ] **ExpressionValidator** — отдельный класс в application/expression_validator.py
- [ ] **MAX_EXPRESSION_DEPTH** = 32 — проверка в RequirementExpression.__post_init__
- [ ] **RuleEvaluationTrace** — содержит rule_code, version_number, effective_from
- [ ] **FK constraint** — organization_overrides.rule_code → compliance.rules(rule_code)
- [ ] **Missing indexes** — idx_overrides_rule_code, idx_rule_versions_period
- [ ] **Deterministic Resolution** — ResolvedRuleSet отсортирован (effective_from, rule_code)
- [ ] **Integration tests** — repository with test DB, YAML loader (10+ тестов)
- [ ] **API tests** — e2e через HTTP (8+ тестов)
- [ ] **Все тесты проходят** — `pytest backend/compliance/tests/ -v`
- [ ] **0 изменений Platform Layer** — не трогаем `public.companies`, `accounting.*`

### Should have (важно, но не блокирует Stream 3)

- [ ] **In-memory repository** для тестов downstream Streams
- [ ] **Минимум 10 Default Rules** для УСН 6%, УСН 15%, ОСНО, Патент
- [ ] **API documentation** — OpenAPI/Swagger
- [ ] **Logging** — create/publish/override операции логируются
- [ ] **Business Facts registry** — `defaults/business_facts/registry.yaml`

### Must NOT have (запрещено)

- [ ] Зависимость Rules Catalog от Business Events, Business Facts, или Engine Layer
- [ ] Импорт SQLAlchemy в `domain/` или `application/interfaces.py`
- [ ] Использование `company_id`, `client_id` вместо `organization_id`
- [ ] Изменение `public.companies` или `accounting.*`
- [ ] Хранение Default Rules в БД как единственный источник (Git — source of truth)
- [ ] Мутация RuleVersion после PUBLISHED

---

## 13. Out of Scope

Что **НЕ входит** в Stream 2 и будет обработано в следующих Streams
(либо не будет никогда):

| Тема | Куда перенесено | Причина |
|:-----|:----------------|:--------|
| **Eligibility Engine** (решение "должен ли отчёт существовать?") | Stream 5 | Отдельный алгоритм, не Rules Catalog |
| **Dependency Engine** (readiness check) | Stream 6 | Зависит от Rules + Facts + Events |
| **Business Facts Engine** | Stream 4 | Stream 2 только определяет FACT-ссылки, не вычисляет |
| **Business Events** | Stream 3 | Не нужно для определения правил |
| **UI для редактирования Overrides** | Stream 9 или отдельный Admin UI | Stream 2 — backend-first |
| **UI для просмотра Default Rules** | Stream 9 | Требует Reporting Workspace |
| **Кэширование результатов Resolver** | Stream 5 (Eligibility Cache) | Опционально, не базовый функционал |
| **История изменений Override** | Stream 3 (Business Events) | Stream 2 хранит только текущий Override |
| **Авторизация (кто может менять rules/overrides)** | Platform Layer / отдельный ADR | Не часть Compliance |
| **Автоматическое обновление Default Rules** (Git → DB sync) | После Stream 11 | CI/CD процесс, не функциональность |
| **Rule impact analysis** ("какие организации пострадают от изменения") | Stream 7 (Simulation Engine) | Требует Simulation |
| **Multi-language rule descriptions** | Stream 9 | Локализация — UI-уровень |
| **Audit log for rule changes** | Stream 3 (Business Events) | Events как единый audit trail |

---

## Приложение A: Сравнение с существующей моделью

| Аспект | До Stream 2 | После Stream 2 |
|:-------|:------------|:---------------|
| Правила | Нет как сущности, только TaxRegime enum | ComplianceRule + RuleVersion + EffectivePeriod |
| Сроки | Нет | DueRule (offset/expression/cron) |
| Требования | Нет | RequirementExpression AST (ALL/ANY/NOT/FACT) |
| Применимость | TaxRegime → что-то? | `applies_to_tax_regimes`, `entity_types`, `regions` |
| Override | Нет | OrganizationOverride с source (default/manual/import/law) |
| Версионность | Нет | Rule → RuleVersion, immutable после publish |
| Валидация | Нет | Startup validation: cycles, facts, overlaps |
| Трассировка | Нет | RuleEvaluationTrace — дерево результатов |
| Источник правил | Код / хардкод | YAML в Git (Default) + DB (Override) |
| Интеграция с Stream 1 | — | `IOrganizationProfileRepository` + `IRulesResolver` |

## Приложение B: ADR-ссылки для Stream 2

| ADR | Статус |
|:----|:-------|
|| ADR-010: Rule Versioning | Создать |
|| ADR-011: Rule Storage (YAML defaults + DB overrides) | Создать |
|| ADR-012: Override Priority (LAW > MANUAL > IMPORT > DEFAULT) | Создать |
|| ADR-013: Requirement Expression AST | Создать |
|| ADR-014: Rule Evaluation Trace | Создать |
|| ADR-015: DueRule Model | Создать |
|| ADR-016: RulesResolver Architecture | Создать |
