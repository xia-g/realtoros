# ADR-002: Runtime Business Facts, политика кэширования и инвалидации

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting  
**Автор:** Architect (RealtorOS)

---

## Контекст

Business Facts Engine должен отвечать на вопрос: "какие бизнес-факты подтверждены для данной организации?" Если хранить факты в БД, возникает риск рассинхронизации: Accounting изменился, а Fact устарел. Если вычислять каждый раз — нагрузка на чтение accounting_entries и business_events.

## Решение

### 1. Business Facts — вычисляемые на лету, не хранимые

Business Facts Engine возвращает **BusinessFactResult** исключительно в runtime:

```python
def evaluate_business_facts(
    organization: OrganizationProfile,
    business_events: list[BusinessEvent],
    accounting_entries: list[AccountingEntry],
    facts: list[BusinessFact],
) -> dict[str, BusinessFactResult]:
    # Чистая функция: input → output, без side effects
```

- Нет таблицы `business_fact_results`
- Нет DDL для хранения фактов
- BusinessFactResult — transient, только в памяти

### 2. Опциональный кэш с явной инвалидацией

Кэш — исключительно для производительности, не источник истины.

```
┌─────────────────────────────┐
│  Business Facts Engine      │
│  (always fresh computation) │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Cache (Redis / in-memory)  │
│  TTL: 60s                   │
│  Invalidated on:            │
│    • new BusinessEvent      │
│    • new AccountingEntry    │
│    • OrganizationProfile    │
│       change                │
└─────────────────────────────┘
```

**Политика инвалидации:**

| Событие | Инвалидация |
|:--------|:------------|
| Новый BusinessEvent (любой тип) | Сброс кэша фактов для organization_id + period |
| Новый AccountingEntry | Сброс кэша фактов для organization_id + period |
| Изменение OrganizationProfile | Полный сброс кэша для organization_id |
| Изменение Default Rules (деплой) | Полный сброс для всех организаций |

### 3. Provenance (происхождение)

Каждый подтверждённый факт возвращает полную цепочку происхождения:

```
fact: "revenue_posted"
  verified_from: "accounting_entry"
  accounting_entry_id: "revenue_06_2026"
  event_id: null
  document_id: null (Compliance не знает о документах)
```

Compliance проверяет только Business Events и Accounting Entries, НЕ документы.

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Хранить факты в БД** | Рассинхронизация с Accounting, stale data, сложные миграции |
| **Всегда вычислять на лету** | Дополнительная нагрузка на чтение (mitigation: кэш) |
| **Runtime + optional cache** | Нет риска рассинхронизации, производительность за счёт кэша |

## Последствия

**Positive:**
- Business Fact Result всегда свежий (источник истины — Accounting)
- Нет риска рассинхронизации между хранимыми и реальными данными
- Кэш — простая оптимизация, потеря кэша не страшна
- Provenance даёт полную прозрачность

**Negative:**
- Каждый запрос Dependency Engine триггерит перевычисление фактов (mitigation: кэш с TTL)
- Кэш нужно инвалидировать при любом изменении Accounting/Events
- При старте системы после простоя кэш пуст — первый запрос будет медленным

## Связанные решения

- ADR-001: Business Events как источник изменений
- ADR-003: Rules Catalog и Default vs Override
