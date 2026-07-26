# ADR-010: Rule Versioning — ComplianceRule → RuleVersion → EffectivePeriod

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting, Stream 2  
**Автор:** Architect (RealtorOS)

---

## Контекст

Налоговые и отчётные правила меняются каждый год: новые ставки, новые формы деклараций, изменения в НК РФ. Организации должны применять **ту версию правила, которая действовала в отчётном периоде**, а не текущую.

Без версионирования:
- Нельзя определить, какая редакция правила применялась к отчёту за 2025 год
- Изменение правила «на лету» ломает уже сформированную отчётность
- Нет истории: кто, когда и зачем изменил правило

## Решение

### 1. Модель: ComplianceRule → RuleVersion

```python
ComplianceRule (абстрактное описание)
    │
    ├── RuleVersion v1: effective_from=2024-01-01, effective_to=2025-12-31
    ├── RuleVersion v2: effective_from=2026-01-01, effective_to=None
    └── RuleVersion v3: effective_from=2027-01-01, effective_to=None
```

- **ComplianceRule** — абстрактное описание нормы/требования (метаданные: название, тип, категория, статус)
- **RuleVersion** — конкретная редакция с содержанием (requirement_expression, due_rule, applies_to, effective_period)
- **RuleVersion immutable после публикации** — ни одно поле не меняется

### 2. Монотонный version_number

- `version_number` — целое число, 1, 2, 3... монотонно возрастает для одного rule_code
- Гарантируется `uq_rule_versions_rule_version UNIQUE (rule_code, version_number)`

### 3. effective_from / effective_to — полуинтервал [from, to)

- `effective_from`: дата начала действия (включительно)
- `effective_to`: дата окончания действия (не включая эту дату, NULL = бессрочно)
- Проверка: `effective_from < effective_to` (если effective_to не NULL)
- Инвариант: ни один момент времени не может быть покрыт двумя версиями одного rule_code

### 4. Runtime overlap check при публикации

`RuleCatalogService.publish_version()` атомарно проверяет:
- Пересечение `[effective_from, effective_to)` с существующими PUBLISHED версиями
- Только для того же `rule_code`
- В одной транзакции: загрузка всех версий → проверка → INSERT

### 5. Жизненный цикл

```
DRAFT → PUBLISHED → DEPRECATED → ARCHIVED
```

- DRAFT → PUBLISHED: создаётся RuleVersion, статус правила → PUBLISHED
- PUBLISHED — immutable; нельзя вернуть в DRAFT
- DEPRECATED → ARCHIVED: разрешён; обратный переход — нет

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Только текущая версия** | Невозможно определить применимость к прошлым периодам; изменение правила ломает историю |
| **Версии по годам** (rule_2024, rule_2025) | Дублирование кода, ручное переключение, нарушение DRY |
| **effective_from/effective_to + immutable Version** | Автоматический выбор версии по дате; полная история; no `if year == 2026` |

## Последствия

**Positive:**
- Автоматический выбор версии по `at_date`: `effective_from <= at_date < effective_to`
- Полная история изменений — аудит без дополнительных таблиц
- Immutable version гарантирует: отчёт за 2025 не изменится при обновлении правила в 2026

**Negative:**
- Дополнительная сложность при публикации: runtime overlap check обязателен
- Рост таблицы `rule_versions` при частых изменениях (mitigation: партиционирование не требуется — объём мал)

## Связанные решения

- ADR-011: Rule Storage (YAML defaults + DB overrides) — где хранятся версии
- ADR-016: RulesResolver Architecture — как выбирается активная версия
- ADR-014: Rule Evaluation Trace — какая версия была применена
