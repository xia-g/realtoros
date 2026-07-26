# ADR-006: Event Versioning, Rule Evaluation Trace, Task Provenance, Eligibility Cache, Rules Catalog Validation

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting  
**Автор:** Architect (RealtorOS)

---

## Контекст

В ходе финального ревью архитектуры Epic 3 перед реализацией выявлены пять сквозных аспектов, требующих явного закрепления:

1. **Event Versioning** — append-only журнал Business Events не имеет механизма для безопасной эволюции формата событий.
2. **Rule Evaluation Trace** — RequirementExpression не возвращает трассировку, что усложняет Explainability.
3. **Task Provenance** — Task не хранит источник происхождения, что затрудняет аудит.
4. **Eligibility Cache** — отдельная стратегия кэширования не описана для Eligibility Engine.
5. **Rules Catalog Validation** — отсутствует валидация каталога правил при запуске, ошибки в YAML/правилах будут обнаружены только в runtime.

## Решения

### 1. Event Versioning

Каждое событие в append-only журнале содержит поле `event_schema_version: int`.

```python
@dataclass
class BusinessEvent:
    event_id: str
    organization_id: UUID
    period: str
    timestamp: datetime
    source: str
    event_schema_version: int   # ← версия схемы
    metadata: dict
```

```sql
CREATE TABLE business_events (
    event_id TEXT PRIMARY KEY,
    ...
    event_schema_version INTEGER NOT NULL DEFAULT 1,  -- ← новая колонка
    ...
);
```

**Правила эволюции:**

| Версия | Изменение | Обратная совместимость |
|:-------|:----------|:-----------------------|
| 1 → 2 | Новое поле в metadata | ✅ Да (default null) |
| 1 → 2 | Новое обязательное поле | ❌ Нет (новый парсер) |
| 1 → 2 | Удаление поля | ❌ Нет (старые consumer'ы сломаются) |

- Consumers читают `event_schema_version` и выбирают соответствующий парсер/адаптер.
- При неизвестной версии — fallback: логирование warning + обработка по версии 1.
- Миграция данных: не требуется, т.к. новые события пишутся с новой версией.

### 2. Rule Evaluation Trace

После вычисления RequirementExpression возвращается не только итоговый статус, но и дерево трассировки.

```python
@dataclass
class RuleEvaluationTrace:
    expression_type: Literal["ALL", "ANY", "NOT", "FACT"]
    fact_code: str | None          # для FACT — какой бизнес-факт
    status: Literal["confirmed", "missing", "disputed", "skipped"]
    children: list[RuleEvaluationTrace]  # рекурсивная структура
    detail: str | None             # пояснение
```

**Пример:**
```
ALL
├── revenue_posted ✔
├── expenses ✔
└── period_closed ✘
    └── detail: "Событие period_closed за июнь отсутствует"
```

**Потребители трассировки:**
- Explainability API (ReasoningGraphBuilder использует trace вместо повторного обхода AST)
- Dashboard (UI может показать дерево без повторного вычисления)
- Simulation Engine (строит projected trace для simulated действий)

Trace — структура данных (не лог), вычисляется однократно при evaluate_expression() и передаётся вместе с DependencyReport.

### 3. Task Provenance

Task содержит поле `generated_from`, указывающее источник происхождения.

```python
@dataclass
class Task:
    task_id: str
    ...
    auto_generated: bool
    generated_from: str | None    # "report" | "requirement" | "simulation" | "manual"
    tags: list[str]
```

| Значение | Источник | Пример |
|:---------|:---------|:-------|
| `report` | Generated from a ReportDefinition deadline | "Сдать декларацию УСН до 25 окт" |
| `requirement` | Generated from an unmet requirement | "Провести зарплату — требуется для 6-НДФЛ" |
| `simulation` | Generated from Simulation Engine recommendation | "Закрыть период — симуляция показала улучшение" |
| `manual` | Created manually by the accountant | "Позвонить в налоговую" |

**Зачем:** Без `generated_from` невозможно отфильтровать автоматические задачи от ручных, а также понять, какой компонент системы породил задачу.

### 4. Eligibility Cache

Eligibility Engine может быть дорогим при большом количестве правил (проверка tax_regime, has_vat, entity_type, region, региональные льготы).

**Стратегия кэширования (аналогично Business Facts, ADR-002):**

```
Eligibility Engine
    │
    ▼
Cache (Redis / in-memory)
    TTL: 60s
    Key: eligibility:{organization_id}:{report_code}
    Value: EligibilityResult
```

| Событие | Инвалидация |
|:--------|:------------|
| Изменение OrganizationProfile | Сброс всех eligibility для organization_id |
| Изменение Default Rules (деплой) | Полный сброс для всех организаций |
| Добавление/изменение Override | Сброс eligibility для organization_id |

- Кэш — опционален, потеря кэша не страшна (всегда можно пересчитать).
- При пустом кэше после старта — первый запрос будет медленным (cold start).
- TTL защищает от устаревших данных при пропущенных событиях инвалидации.

### 5. Rules Catalog Validation

Отдельный валидатор, запускаемый при старте Compliance сервиса (и опционально в CI при изменении `rules_catalog.yaml`).

**Проверки:**

| Проверка | Описание | Ошибка |
|:---------|:---------|:-------|
| Cycles in RequirementExpression | Обход AST графа, поиск циклов (ALL → ALL → ALL → ...) | "Циклическая зависимость в requirement_expression для report_code=usn_declaration" |
| Fact code references | Каждый FACT-узел в RequirementExpression ссылается на существующий BusinessFact | "fact_code=revenue_posted не найден в business_facts" |
| Overlapping effective dates | Два правила с одинаковым кода перекрываются по effective_from/effective_to без Override | "Перекрытие effective_from/effective_to для requirement_code=req_revenue" |
| DueRule correctness | Парсинг DueRule: offset, expression, cron | "Невалидный offset: +3M 32d (день > 31)" |
| Conflicting Override | Два Override для одного report_code + period с разными значениями | "Конфликтующие Override для usn_declaration/2026" |

**Режимы:**
- **startup** — полная валидация блокирует запуск сервиса
- **CI/CD** — валидация при pull request в `rules_catalog.yaml` (gate для CI)
- **runtime** — валидация Organization Override при сохранении (через API)

Ошибки валидации возвращаются единым отчётом:
```json
{
  "valid": false,
  "errors": [
    {"code": "CYCLE_DETECTED", "path": "reports.usn_declaration.requirement_expression", "detail": "..."},
    {"code": "FACT_NOT_FOUND", "path": "reports.balance.requirement_expression.children[0]", "detail": "..."}
  ]
}
```

## Обоснование

| Аспект | Без решения | С решением |
|:-------|:------------|:-----------|
| Event Versioning | Невозможно изменить формат событий без ломающей миграции всей БД | Версионирование на уровне записи, consumers адаптируются |
| Rule Evaluation Trace | Explainability вынуждена повторно обходить AST для построения графа | Trace вычисляется однократно, переиспользуется всеми потребителями |
| Task Provenance | Невозможно отличить ручные задачи от автоматических, сложный аудит | generated_from даёт полную прозрачность источника |
| Eligibility Cache | Каждый запрос пересчитывает eligibility для всех отчётов | TTL-кэш с инвалидацией по событиям |
| Rules Catalog Validation | Ошибки в YAML/правилах обнаруживаются в runtime (пользователем) | Ошибки ловятся при старте/деплое, zero runtime surprises |

## Последствия

**Positive:**
- Безопасная эволюция событий без ломающих миграций
- Explainability использует готовую трассировку вместо повторного обхода
- Полная прозрачность происхождения задач
- Производительность за счёт кэша eligibility
- Zero runtime surprises за счёт startup validation

**Negative:**
- Дополнительное поле `event_schema_version` в каждом событии (небольшой overhead)
- RuleEvaluationTrace увеличивает размер DependencyReport (mitigation: опциональное включение)
- Валидация adds startup latency (mitigation: фоновый запуск + кэширование результата)
- Eligibility Cache требует интеграции с event bus для инвалидации

## Связанные решения

- ADR-001: Business Events (расширение: event_schema_version)
- ADR-002: Runtime Business Facts и политика кэширования (аналогия для Eligibility Cache)
- ADR-003: Rules Catalog (валидация effective_from/effective_to и Override)
- ADR-004: Explainability Pipeline (RuleEvaluationTrace как вход ReasoningGraphBuilder)
