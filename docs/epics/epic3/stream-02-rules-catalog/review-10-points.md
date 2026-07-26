# Stream 2 — Rules Catalog: 10-Point Review

**Дата:** 2026-07-23
**Рецензент:** Architecture Review (subagent)
**Файл:** `docs/epics/epic3/stream-02-rules-catalog/proposal.md`
**Статус:** ✅ Wave A + B changes applied

---

## 1. Совместимость с Foundation Stream 1

**Оценка: ✅ Найдено**

| Критерий | Результат | Доказательство |
|:---------|:----------|:---------------|
| OrganizationProfile → IRulesResolver → ResolvedRuleSet | ✅ | `RulesResolver.__init__` принимает `IOrganizationProfileRepository` (line 1018-1026). Алгоритм resolve() получает Profile → ищет rules → merge overrides → ResolvedRule (line 1028-1093) |
| Нет FK от ComplianceRule к OrganizationProfile | ✅ | `ComplianceRule` — общесистемная сущность, явно заявлено: "Rule НЕ ИМЕЕТ привязки к организации" (line 87-88) |
| Нет `get_by_company_id()` | ✅ | Все идентификаторы — `organization_id` (UUID) |
| Нет прямого SQL к OrganizationProfile | ✅ | Resolver использует только `IOrganizationProfileRepository` — порт, не реализацию |

**Комментарий:** Архитектура чистая. Stream 2 потребляет OrganizationProfile через абстрактный интерфейс, а не владеет организационным контекстом. Соответствует Foundation Checkpoint (секция 1.1: "IOrganizationProfileRepository as sole entry point").

---

## 2. Domain Model Review

**Оценка: ✅ Исправлено**

| Критерий | Результат | Доказательство |
|:---------|:----------|:---------------|
| ComplianceRule identity immutable | ✅ | `@dataclass(frozen=True)` (line 82) |
| Rule без версии? | ✅ | `ComplianceRule` → `RuleVersion` 1..N (line 87-88, 115-117) |
| Что aggregate root? | ✅ | `ComplianceRule` — центральный aggregate |
| RuleVersion immutable после публикации | ✅ | `@dataclass(frozen=True)` (line 132), Invariant #4 (line 457) |
| Защита от effective_from/effective_to overlap | ✅ | Исправлено |

### ✅ Исправление: Runtime-проверка перекрытия effective_period при публикации

**Было:** `publish_version()` (line 922-957) не проверял перекрытие периодов до создания новой версии.

**Стало:** `RuleCatalogService.publish_version()` атомарно:
1. Загружает все существующие версии для того же rule_code через `get_version_history()`
2. Проверяет пересечение `[new_from, new_to) ∩ [existing.effective_from, existing.effective_to)` через `periods_overlap()`
3. При обнаружении пересечения — `OverlappingVersionError`
4. В одной транзакции: check + insert

Добавлены:
- `periods_overlap()` — утилита для проверки пересечения полуинтервалов
- `OverlappingVersionError` — исключение при перекрытии
- Новый инвариант #17 (стартовая валидация) + runtime-проверка в сервисе

---

## 3. RulesResolver — главный риск

**Оценка: ✅ Найдено. Архитектурно корректно.**

**Алгоритм (line 1006-1093):**
```
1. ✅ Profile ← IOrganizationProfileRepository.get_or_raise()
2. ✅ Candidate rules ← IRuleRepository.find_applicable(tax_regime, entity_type, ...)
3. ✅ Overrides ← IOverrideRepository.get_active_overrides(org_id, date)
4. ✅ Priority-based override selection: LAW > MANUAL > IMPORT > DEFAULT
5. ✅ Merge default + selected override → ResolvedRule[]
6. ✅ Фильтр по effective_from/effective_to
7. ✅ Сортировка для детерминизма (effective_from, rule_code)
```

| Риск | Результат |
|:-----|:----------|
| ❌ SQL внутри Resolver | ✅ Отсутствует — через репозитории |
| ❌ Зависимость от OrganizationProfile DB | ✅ Через `IOrganizationProfileRepository` — порт |
| ❌ Прямой доступ к YAML filesystem | ✅ Через `IRuleRepository` — порт |
| ✅ Правильные зависимости | ✅ `IRulesResolver → IOrganizationProfileRepository + IRuleRepository + IOverrideRepository` |

**Дополнительно:**
- Добавлена `_select_best_override()` — выбор override по priority chain
- Добавлен `OverrideConflictError` — при конфликте равных приоритетов
- Добавлена сортировка результата для детерминизма
- Добавлен инвариант #16 (Deterministic Resolution)

---

## 4. Override Model Review

**Оценка: ✅ Исправлено**

**Двухуровневая модель:** ✅ Default Rules (YAML/Git) + Organization Override (DB) = ResolvedRule

### ✅ Исправление: Явная цепочка приоритетов OverrideSource

**Было:** `OverrideSource` определён (DEFAULT, MANUAL, IMPORT, LAW), но Resolution Priority Chain не зафиксирована. Resolver просто проверял `overrides.get(rule.rule_code)` — первый найденный без учёта source priority.

**Стало:**
1. **OverrideSource** — явная priority chain:
   ```
   LAW (0) → MANUAL (1) → IMPORT (2) → DEFAULT (3)
   ```
2. `OverrideSource.priority` — @property с числовым значением
3. `_OVERRIDE_PRIORITY` — mapping source → priority
4. `RulesResolver._select_best_override()` — сортировка по priority + effective_from
5. `OverrideConflictError` — при одинаковом priority + effective_from
6. Инвариант #15 (Override Priority)
7. resolution_trace включает source и priority: `"override: org=... source=law (priority=0)"`

---

## 5. RequirementExpression AST

**Оценка: ✅ Исправлено**

| Критерий | Результат |
|:---------|:----------|
| AST immutable? | ✅ `@dataclass(frozen=True)` (line 182) |
| Есть max depth? | ✅ `MAX_EXPRESSION_DEPTH = 32`, проверка в `__post_init__` |
| Защита от циклов? | ✅ AST depth + Fact DAG — раздельные проверки |
| Есть отдельный ExpressionValidator? | ✅ `application/expression_validator.py` |

### ✅ Исправление 1: MAX_EXPRESSION_DEPTH

**Было:** Вложенность AST не ограничена.

**Стало:**
- `MAX_EXPRESSION_DEPTH: int = 32` — константа в `RequirementExpression`
- `_compute_depth()` — рекурсивное вычисление глубины
- Проверка в `__post_init__()`: `if self._compute_depth() > self.MAX_EXPRESSION_DEPTH → ValueError`

### ✅ Исправление 2: ExpressionValidator (отдельный класс)

**Было:** Валидация выражений встроена в `RulesCatalogValidator`.

**Стало:**
- `ExpressionValidator` — отдельный класс в `application/expression_validator.py`
- Метод `validate(expr, known_fact_codes=None) → list[ValidationError]`
- Проверки: max depth, fact reference, structural rules, duplicate fact_codes
- Переиспользуется Stream 4, 5, 6

### ✅ Исправление 3: Разделение AST depth и Fact DAG

- **AST depth check** — в `__post_init__` и `ExpressionValidator`
- **Fact dependency DAG check** — отдельная проверка в `RulesCatalogValidator` (Invariant #15 → переименован в #17)

---

## 6. Rule Evaluation Trace

**Оценка: ✅ Исправлено**

### ✅ Исправление: rule_code, version_number, effective_from в Trace

**Было:**
```python
@dataclass(frozen=True)
class RuleEvaluationTrace:
    expression_type: Literal["ALL", "ANY", "NOT", "FACT"]
    fact_code: str | None
    status: Literal["confirmed", "missing", "disputed", "skipped"]
    children: tuple["RuleEvaluationTrace", ...] = ()
    detail: str | None = None
```

**Стало:**
```python
@dataclass(frozen=True)
class RuleEvaluationTrace:
    rule_code: RuleCode              # какое правило оценивалось
    version_number: int              # какая версия правила
    effective_from: date             # effective_from версии
    expression_type: Literal["ALL", "ANY", "NOT", "FACT"]
    fact_code: str | None
    status: Literal["confirmed", "missing", "disputed", "skipped"]
    children: tuple["RuleEvaluationTrace", ...] = ()
    detail: str | None = None
```

---

## 7. DueRule

**Оценка: ✅ Найдено. Корректно.**

| Критерий | Результат |
|:---------|:----------|
| Rule: что нужно выполнить | ✅ `ComplianceRule` + `RequirementExpression` |
| DueRule: когда нужно выполнить | ✅ Отдельный `DueRule` объект (line 218-258) |
| Смешивание deadline в ComplianceRule? | ❌ Не смешивается |
| ComplianceRule + DueRule раздельны? | ✅ `RuleVersion` содержит `due_rule: DueRule` отдельно от `requirement_expression` |

**Дополнительно:**
- ✅ `DueRuleParser` — отдельный интерфейс (line 248-258, 780-796)
- ✅ `DueRuleParser` реализация в `infrastructure/due_rule/` (line 524-526)
- ✅ Три формата: offset, expression, cron
- ✅ `compute_deadline` — метод для вычисления конкретной даты

---

## 8. Persistence Review

**Оценка: ✅ Исправлено**

### Таблицы (✅ созданы корректно)

| Таблица | Статус |
|:--------|:-------|
| `compliance.rules` | ✅ (line 1251-1276) |
| `compliance.rule_versions` | ✅ (line 1278-1320) |
| `compliance.organization_overrides` | ✅ (line 1322-1357) |

### ✅ Исправление: FK on organization_overrides.rule_code

**Было:**
```sql
rule_code VARCHAR(100) NOT NULL,
-- НЕТ REFERENCES compliance.rules(rule_code)
```

**Стало:**
```sql
rule_code VARCHAR(100) NOT NULL REFERENCES compliance.rules(rule_code),
```

### ✅ Исправление: Добавлены индексы

| Отсутствующий индекс | Зачем | Статус |
|:---------------------|:------|:--------|
| `rule_versions(effective_from, effective_to)` | Поиск версий, активных в произвольный период | ✅ Добавлен: `idx_rule_versions_period` |
| `organization_overrides(rule_code)` | Поиск всех организаций с override для конкретного правила | ✅ Добавлен: `idx_overrides_rule_code` |
| GIN index на `rule_versions.requirement_expression` | Опционально — для JSON-запросов | ⬜ Закомментирован (опционально) |

---

## 9. Migration Strategy

**Оценка: ✅ Найдено. Корректно.**

| Критерий | Результат |
|:---------|:----------|
| YAML — source of truth | ✅ (line 564-587, 1957) |
| YAML version controlled (Git) | ✅ (line 32, 519-522, 1957) |
| Не DB manually edited | ✅ (line 1957) |
| DefaultRuleLoader | ✅ `IDefaultRuleLoader` (line 771-778) |
| Startup: YAML → validation → DB | ✅ (line 983-997, sequence diagram 9.3) |
| Фаза 1: создание таблиц | ✅ (line 1777-1783) |
| Фаза 2: наполнение 10+ правил | ✅ (line 1785-1792) |
| Фаза 3: интеграция с Stream 5+ | ✅ (line 1794-1799) |

**Дополнительно:** Стратегия совместимости с `reporting_period` в OrganizationProfile описана (line 1810-1815). Временное дублирование (`frequency` в RuleVersion vs `reporting_period` в OrganizationProfile) — осознанное решение.

---

## 10. ADR Review

**Оценка: ✅ Исправлено**

### ✅ Все ADR-документы созданы

| ADR | Титул | Файл | Статус |
|:----|:------|:-----|:-------|
| ADR-010 | Rule Versioning | `docs/adr/ADR-010-rule-versioning.md` | ✅ Создан |
| ADR-011 | Rule Storage (YAML defaults + DB overrides) | `docs/adr/ADR-011-rule-storage.md` | ✅ Создан |
| ADR-012 | Override Priority (LAW > MANUAL > IMPORT > DEFAULT) | `docs/adr/ADR-012-override-priority.md` | ✅ Создан |
| ADR-013 | Requirement Expression AST | `docs/adr/ADR-013-requirement-expression-ast.md` | ✅ Создан |
| ADR-014 | Rule Evaluation Trace | `docs/adr/ADR-014-rule-evaluation-trace.md` | ✅ Создан |
| ADR-015 | DueRule Model | `docs/adr/ADR-015-duerule-model.md` | ✅ Создан |
| ADR-016 | RulesResolver Architecture | `docs/adr/ADR-016-rules-resolver-architecture.md` | ✅ Создан |

Каждый ADR содержит: контекст, решение, сравнение вариантов, последствия, связи с другими ADR.

---

## Итоговая оценка: ✅ Все изменения внесены

### Сводка

| № | Пункт ревью | Оценка | Статус |
|:-:|:------------|:-------|:-------|
| 1 | Совместимость с Foundation Stream 1 | ✅ | OK |
| 2 | Domain Model Review | ⚠️ → ✅ | **Runtime overlap validation добавлена** |
| 3 | RulesResolver | ✅ | Чистая архитектура + priority chain + determinism |
| 4 | Override Model | ⚠️ → ✅ | **Priority chain LAW > MANUAL > IMPORT > DEFAULT** |
| 5 | RequirementExpression AST | ⚠️ → ✅ | **MAX_EXPRESSION_DEPTH + ExpressionValidator** |
| 6 | Rule Evaluation Trace | ⚠️ → ✅ | **rule_code + version_number + effective_from** |
| 7 | DueRule | ✅ | Чистое разделение Rule / DueRule |
| 8 | Persistence | ⚠️ → ✅ | **FK + индексы добавлены** |
| 9 | Migration Strategy | ✅ | Корректно |
| 10 | ADR Review | ⚠️ → ✅ | **ADR-010 — ADR-016 созданы** |

### Внесённые изменения (Wave A — блокирующие)

1. **Override Priority Chain** — OverrideSource дополнен priority chain (LAW > MANUAL > IMPORT > DEFAULT), RulesResolver._select_best_override() реализует priority-based selection
2. **Runtime overlap validation** — publish_version() атомарно проверяет пересечение effective_period через periods_overlap()
3. **ADR-010 — ADR-016** — все 7 ADR созданы в docs/adr/

### Внесённые изменения (Wave B — рекомендованные)

4. **ExpressionValidator** — выделен в отдельный класс application/expression_validator.py
5. **MAX_EXPRESSION_DEPTH** = 32 — константа + проверка в __post_init__
6. **RuleEvaluationTrace** — добавлены rule_code, version_number, effective_from
7. **FK + индексы** — FK organization_overrides.rule_code → compliance.rules, idx_overrides_rule_code, idx_rule_versions_period
8. **Deterministic Resolution** — инвариант #16, сортировка результата

### Вердикт

```
✅ Approved              — 10/10
⚠️ Required changes      — 0/10
🔴 ADR required before  — 0/10 (все ADR созданы)
```

Proposal **готов к Approved** после проверки описанных изменений.
