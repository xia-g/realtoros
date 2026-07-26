# ADR-001: Business Events как append-only журнал, отмена через компенсирующие события

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting  
**Автор:** Architect (RealtorOS)

---

## Контекст

Compliance Layer должен реагировать на изменения в учёте: закрытие периодов, начисление зарплаты, расчёт НДС. Эти изменения поступают из разных сервисов (Accounting, Payroll, Inventory). Без единого источника событий Compliance вынужден либо сканировать сырые данные (нарушение границ доменов), либо работать с устаревшим состоянием.

## Решение

### 1. Business Events — append-only immutable log

Все изменения состояния Compliance фиксируются как **Business Events** в append-only журнале.

```python
@dataclass
class BusinessEvent:
    event_id: str
    organization_id: UUID
    period: str
    timestamp: datetime
    source: str
    event_schema_version: int = 1   # версия схемы (для безопасной эволюции)
    metadata: dict

    # INVARIANT: Никогда не обновляется. Append only.
```

- НЕТ UPDATE
- НЕТ DELETE
- Единственная операция: INSERT

### 2. Иерархия классов

```
BusinessEvent (базовый)
├── AccountingEvent      # события из учёта
│   ├── PERIOD_CLOSED
│   ├── VAT_CALCULATED
│   ├── PAYROLL_POSTED
│   ├── YEAR_CLOSED
│   ├── INVENTORY_COMPLETED
│   ├── TAX_PAYMENT_RECORDED
│   └── PERIOD_REOPENED
└── ComplianceEvent      # события из Compliance
    ├── REPORT_SUBMITTED
    ├── REPORT_AMENDED
    └── COMPLIANCE_CHECK_TRIGGERED
```

Хранение в одной таблице с полем `event_class` (`accounting` | `compliance`).

### 3. Компенсирующие события

Единственный способ "отменить" событие — создать компенсирующее:

| Исходное | Компенсирующее |
|:---------|:---------------|
| PERIOD_CLOSED | PERIOD_REOPENED |
| YEAR_CLOSED | YEAR_REOPENED |
| REPORT_SUBMITTED | REPORT_AMENDED |

Это сохраняет append-only инвариант и даёт полный аудит.

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **UPDATE/DELETE** | Потеря аудита, невозможно восстановить историю |
| **Soft-delete** | Сложные запросы, риск утечки данных |
| **Append-only + компенсация** | Полный аудит, простая модель, детерминированное воспроизведение состояния |

## Последствия

**Positive:**
- Полный аудит всех изменений
- Детерминированное воспроизведение состояния на любой момент времени
- Простая модель хранения (один INSERT, никаких UPDATE/DELETE)
- Компенсирующие события дают семантическую отмену без нарушения инварианта

**Negative:**
- Рост таблицы business_events (mitigation: партиционирование по месяцам)
- Нужна валидация: PERIOD_REOPENED не может появиться без предшествующего PERIOD_CLOSED
- Компенсирующие события требуют явной обработки в Business Facts Engine

## Связанные решения

- ADR-002: Runtime Business Facts и кэширование
- ADR-005: organization_id как граница изоляции
