# ADR-011: Rule Storage — YAML Defaults + Database Overrides

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting, Stream 2  
**Автор:** Architect (RealtorOS)

---

## Контекст

Правила Compliance имеют два принципиально разных источника:

1. **Default Rules** — общесистемные правила, определяемые законодательством (НК РФ, региональные законы). Они одинаковы для всех организаций одного налогового режима. Должны проходить code review перед изменением.
2. **Organization Overrides** — специфические для организации переопределения (региональные льготы, индивидуальные сроки, импорт из внешних систем). Должны меняться быстро, через UI, без деплоя.

Как хранить эти два типа данных без дублирования и нарушения целостности?

## Решение

### 1. Двухуровневое хранение

```
┌─────────────────────────────────────────────────────┐
│                    Default Rules                     │
│  YAML/JSON в Git (backend/compliance/defaults/)     │
│  • Source of truth                                  │
│  • Code review через PR                             │
│  • Версионируется вместе с кодом                     │
│  • Загружается при старте / деплое                   │
└──────────────────────┬──────────────────────────────┘
                       │ загрузка + валидация
                       ▼
┌─────────────────────────────────────────────────────┐
│                   Database (кэш)                     │
│  compliance.rules + compliance.rule_versions         │
│  • Кэш Default Rules для быстрого доступа            │
│  • Git — source of truth, DB — read-optimised cache  │
│  • Обновляется при reload_defaults()                 │
└──────────────────────┬──────────────────────────────┘
                       │ merge
                       ▼
┌─────────────────────────────────────────────────────┐
│                Organization Overrides                │
│  compliance.organization_overrides (DB-only)         │
│  • Создаются через API / UI                         │
│  • Всегда в БД, никогда в Git                       │
│  • Переопределяют Default Rules для конкретной org   │
└─────────────────────────────────────────────────────┘
```

### 2. Default Rules — YAML в Git

```
backend/compliance/defaults/
├── index.yaml                  # индекс всех Default Rules
├── business_facts/
│   └── registry.yaml           # реестр бизнес-фактов
└── rules/
    ├── usn/
    │   ├── usn_6.yaml          # УСН 6%
    │   ├── usn_15.yaml         # УСН 15%
    │   └── usn_declaration.yaml
    ├── osno/
    │   ├── profit_tax.yaml
    │   ├── vat_return.yaml
    │   └── property_tax.yaml
    ├── patent/
    │   └── patent_cost.yaml
    └── common/
        ├── insurance.yaml
        ├── 6_ndfl.yaml
        └── rsb.yaml
```

Каждый YAML-файл содержит метаданные правила + одну или несколько версий.

### 3. Organization Overrides — Database

- Хранятся в `compliance.organization_overrides`
- FK: `organization_id → organization_profiles(organization_id)` + `rule_code → rules(rule_code)`
- NULL-поля означают «использовать значение из Default Rule»
- source: manual | import | law

### 4. Загрузка Default Rules (startup / deploy)

```python
async def reload_defaults(self) -> ValidationResult:
    rules, versions = await self._loader.load_all()  # из YAML
    result = validator.validate(rules, versions)
    if result.passed:
        await self._rule_repo.bulk_upsert_rules(rules, versions)
    return result
```

### 5. Правила слияния Default + Override

- Resolver загружает Default Rule из DB (кэш) + Override из DB
- Если Override существует — применяется merge поверх Default
- NULL-поля в Override → используются значения из Default
- Default никогда не меняется под влиянием Override

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Только Git** | Нельзя быстро изменить для конкретной организации; нужен деплой для каждой правки |
| **Только DB** | Нет code review; изменения не версионируются; сложно отследить изменения законодательства |
| **Git + DB (двухуровневая)** | Default Rules проходят code review; Override — быстрые изменения через UI; Git — source of truth |

## Последствия

**Positive:**
- Default Rules: code review, версионирование в Git, единый источник правды
- Override: быстрые изменения без деплоя, специфические для организации
- Git → DB загрузка с валидацией предотвращает повреждённые правила
- NULL-поля в Override экономят хранение (не нужно копировать весь Rule)

**Negative:**
- Риск рассинхронизации Git ↔ DB (mitigation: reload_defaults() при каждом деплое)
- Две таблицы вместо одной — сложнее запросы (mitigation: Resolver абстрагирует merge)
- Override может ссылаться на `rule_code`, который изменился в Git — нужна FK защита и валидация

## Связанные решения

- ADR-010: Rule Versioning — как версии хранятся в Default Rules
- ADR-012: Override Priority — как разрешаются конфликты между Override разных источников
- ADR-016: RulesResolver Architecture — merge Default + Override в ResolvedRule
- ADR-005: Multi-organization isolation — organization_id как граница Override
