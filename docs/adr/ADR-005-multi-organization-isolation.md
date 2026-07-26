# ADR-005: Multi-organization isolation — organization_id как обязательная граница

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting  
**Автор:** Architect (RealtorOS)

---

## Контекст

RealtorOS обслуживает несколько организаций: ИП, ООО, группы компаний, филиалы. Каждая организация имеет свой ИНН, налоговый режим, отчётность, сделки, бухгалтерию. Без явной границы изоляции данные одной организации могут быть случайно доступны другой (cross-org leak), а запросы Compliance — смешивать данные разных организаций.

## Решение

### 1. organization_id — обязательная граница

Все сущности Compliance Layer содержат `organization_id`:

| Entity | organization_id |
|:-------|:----------------|
| OrganizationProfile | ✅ PK |
| BusinessEvent | ✅ обязательное поле |
| BusinessFactResult (runtime) | ✅ в контексте запроса |
| ReportDefinition | ✅ через applies_to + override |
| DependencyReport | ✅ computed per organization_id |
| ComplianceHealth | ✅ computed per organization_id |
| Task | ✅ обязательное поле |
| ComplianceTimeline | ✅ computed per organization_id |

### 2. Все API с organization_id

Каждый endpoint требует `organization_id`:

```
GET    /api/v1/organizations/{organization_id}/...
POST   /api/v1/organizations/{organization_id}/...
```

Нет глобальных endpoint'ов без organization_id.

### 3. Хранение

Все таблицы с organisation_id — FK на organization_profiles:

```sql
CREATE TABLE business_events (
    ...
    organization_id UUID NOT NULL REFERENCES organization_profiles(organization_id)
);

CREATE TABLE organization_rules_overrides (
    ...
    organization_id UUID NOT NULL REFERENCES organization_profiles(organization_id)
);

CREATE TABLE tasks (
    ...
    organization_id UUID NOT NULL REFERENCES organization_profiles(organization_id)
);
```

### 4. Изоляция на уровне запросов

Каждый сервис:
1. Получает `organization_id` из request context
2. Все WHERE-клаузы содержат `organization_id = :org_id`
3. Row-Level Security (RLS) как дополнительный слой защиты:

```sql
ALTER TABLE business_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON business_events
    USING (organization_id = current_setting('app.current_org_id')::UUID);
```

### 5. Кэширование с organisation_id

Кэш ключи включают organization_id:

```
fact_results:{org_id}:{period}
eligibility:{org_id}
timeline:{org_id}
```

Это гарантирует, что данные одной организации не будут случайно возвращены другой.

### 6. Исключения

Только административные endpoint'ы могут не иметь organization_id:

```
GET /api/v1/admin/organizations                      — список всех организаций
POST /api/v1/admin/organizations                     — создать организацию
```

Эти endpoint'ы доступны только с admin-ролью.

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Singleton (одна организация)** | Не поддерживает группы компаний, филиалы, агентства |
| **Отдельная БД на организацию** | Дорого, сложно деплоить, нельзя агрегировать |
| **organization_id как FK + RLS** | Просто, безопасно, масштабируемо |

## Последствия

**Positive:**
- Невозможно случайно смешать данные организаций
- RLS — defence in depth (даже если WHERE забыли)
- Все API самодокументируемы (organization_id обязателен)
- Простая миграция: добавить organisation_id, включить RLS

**Negative:**
- Все запросы требуют organization_id — больше параметров
- RLS может скрыть ошибку: если забыли WHERE organisation_id, RLS спасёт, но может быть медленнее
- Кэш фрагментирован по организациям — больше памяти (mitigation: TTL)
- Нужен админский endpoint без organization_id для управления

## Связанные решения

- ADR-003: Organization Override всегда привязан к organization_id
- ADR-001: Business Events привязаны к organization_id
