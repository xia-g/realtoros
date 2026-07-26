# ADR-016: RulesResolver Architecture — детерминированный merge Default + Override

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting, Stream 2  
**Автор:** Architect (RealtorOS)

---

## Контекст

Rules Resolver — центральный механизм Stream 2. Он определяет, какие правила применимы к организации в заданный момент времени. Resolver используется всеми downstream Streams (5, 6, 8).

Требования:
- **Детерминированность**: одинаковые входные данные → одинаковый упорядоченный результат
- **Двухуровневость**: merge Default Rules + Organization Overrides
- **Priority chain**: LAW > MANUAL > IMPORT > DEFAULT
- **Производительность**: resolve() должен быть быстрым (вызывается для каждой организации, каждого периода)
- **Тестируемость**: все зависимости — через интерфейсы (порты)

## Решение

### 1. Архитектура

```
┌───────────────────────────────────────────────────────────────────┐
│                        RulesResolver                              │
│                                                                   │
│  1. Get OrganizationProfile                                       │
│     └── IOrganizationProfileRepository.get_or_raise()             │
│                                                                   │
│  2. Find applicable default rules                                 │
│     └── IRuleRepository.find_applicable(tax_regime, type, ...)   │
│                                                                   │
│  3. Get all active overrides for org                              │
│     └── IOverrideRepository.get_active_overrides(org_id, date)    │
│                                                                   │
│  4. For each rule, select best override by priority chain         │
│     └── _select_best_override(overrides)                          │
│                                                                   │
│  5. Merge Default + selected Override → ResolvedRule              │
│     └── Merge rules:                                              │
│         - requirement_expression: override ?? default             │
│         - due_rule: override ?? default                           │
│         - effective_period: intersection of both                  │
│                                                                   │
│  6. Sort for determinism                                          │
│     └── sort by (effective_from, rule_code)                       │
│                                                                   │
│  7. Return ResolvedRule[]                                         │
└───────────────────────────────────────────────────────────────────┘
```

### 2. Зависимости (интерфейсы)

```python
class RulesResolver:
    def __init__(
        self,
        org_repo: IOrganizationProfileRepository,    # Stream 1 — порт
        rule_repo: IRuleRepository,                   # Default Rules (кэш)
        override_repo: IOverrideRepository,            # Organization Overrides (DB)
    ):
        ...

    async def resolve(
        self,
        organization_id: UUID,
        at_date: date | None = None,
    ) -> list[ResolvedRule]:
        ...
```

- Resolver **не зависит** от SQLAlchemy, Git, или конкретных репозиториев
- Все зависимости — через абстрактные интерфейсы в `application/interfaces.py`

### 3. Детерминированность

Инвариант: при одинаковых входных данных (profile, date, catalog version, all overrides) Resolver **всегда** возвращает идентичный упорядоченный результат.

Обеспечивается:
1. **Priority-based override selection**: явный порядок сортировки (priority asc, effective_from desc)
2. **Фиксированный порядок результата**: сортировка по `(effective_from asc, rule_code asc)`
3. **Детерминированные коллекции**: Repository возвращает `list`, а не `set` или `dict`

### 4. Merge-правила

| Поле | Default | Override | Результат |
|:-----|:--------|:---------|:----------|
| requirement_expression | Есть | None → default | default.requirement_expression |
| requirement_expression | Есть | Есть → override | override.requirement_expression |
| due_rule | Есть | None → default | default.due_rule |
| due_rule | Есть | Есть → override | override.due_rule |
| effective_from | from_def | from_ov | max(from_def, from_ov) |
| effective_to | to_def | to_ov | min(to_def, to_ov) |

### 5. Priority-based override selection

```python
@staticmethod
def _select_best_override(overrides: list[OrganizationOverride]) -> OrganizationOverride | None:
    # Sort by: 1) priority (ascending — lower = higher priority)
    #          2) effective_from descending (newest first)
    sorted_ovs = sorted(
        overrides,
        key=lambda ov: (ov.source.priority, -ov.effective_from.toordinal()),
    )
    best = sorted_ovs[0]
    # Conflict check: same priority AND same effective_from
    for ov in sorted_ovs[1:]:
        if ov.source.priority == best.source.priority and ov.effective_from == best.effective_from:
            raise OverrideConflictError(...)
    return best
```

### 6. ResolvedRule (результат)

```python
@dataclass(frozen=True)
class ResolvedRule:
    rule_code: RuleCode
    rule_name: str
    rule_version: RuleVersion
    override: OrganizationOverride | None = None
    requirement_expression: RequirementExpression
    due_rule: DueRule
    effective_from: date
    effective_to: date | None
    resolution_trace: list[str]  # ["default: usn_declaration v3", "override: org=... source=law (priority=0)"]
```

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Inline merge в сервисе** | Нарушение SRP; смешивание логики разрешения и управления правилами |
| **Только Default Rules** | Организации не могут переопределять правила — нарушение бизнес-требования |
| **Resolver как отдельный класс с портами** | Чистая архитектура, тестируемость, детерминированность, переиспользование |

## Последствия

**Positive:**
- Детерминированный результат — предсказуемое поведение для downstream Streams
- Чистая архитектура: Resolver не знает о SQL, Git, HTTP
- Легко тестировать: все зависимости — mock-интерфейсы
- Priority chain защищает от конфликтов override
- Resolution trace даёт прозрачность: какое правило + какой override применён

**Negative:**
- Resolver выполняет N+1 запросов: 1 org + 1 rules + 1 overrides (mitigation: batching в репозиториях)
- Сортировка результата — дополнительный O(n log n) (mitigation: n мало — десятки правил)
- OverrideConflictError — runtime, а не design-time (mitigation: валидация при создании override)

## Связанные решения

- ADR-010: Rule Versioning — RuleVersion как часть ResolvedRule
- ADR-011: Rule Storage — два репозитория: IRuleRepository + IOverrideRepository
- ADR-012: Override Priority — _select_best_override реализует priority chain
- ADR-013: Requirement Expression AST — как передаётся выражение
- ADR-014: Rule Evaluation Trace — resolution_trace в ResolvedRule
- ADR-005: Multi-organization isolation — organization_id как граница resolve
