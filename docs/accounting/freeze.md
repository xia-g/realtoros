# Accounting Core — Architecture Freeze

**Дата:** 2026-06-15
**Статус:** ❄️ ЗАФИКСИРОВАНО (не менять без ADR)
**Версия:** 1.0.0

---

## 1. Стабильный домен (не трогать)

### Таблицы ядра

| Таблица | Назначение |
|---------|-----------|
| `accounting_event` | Accounting Event Journal — версионированный журнал |
| `accounting_decision` | Результат применения правил |
| `decision_explanation` | Детализация каждого правила |
| `recognition_snapshot` | Immutable слепок входных данных |
| `accounting_batch` | Группировка событий (импорт / откат / пересчёт) |
| `tax_regime` | Налоговые режимы компании |
| `tax_period` | Фискальные периоды |
| `event_transaction` | Связь event → bank_transaction |
| `event_document` | Связь event → document |

### Статусные модели (enums)

| Модель | Значения |
|--------|----------|
| `processing_state` | NEW → RECOGNIZING → READY_FOR_DECISION → DECIDING → DONE / FAILED |
| `decision_state` | PENDING, INCLUDED, EXCLUDED, REVIEW_REQUIRED |
| `recognition_status` | pending, recognized, confirmed, rejected |
| `superseded_reason` | ocr_correction, manual_fix, rule_change, document_updated, bank_reimport, recalculation |

### Инварианты

1. `Decision = f(Event, Snapshot, RulesetVersion)` — Rule Engine читает ТОЛЬКО снимки
2. **immutable**: UPDATE запрещён — исправление = новая версия
3. **versioned**: версия, superseded_by, superseded_reason, is_current
4. **replayable**: ReplayService.recalculate() даёт идентичный результат при тех же данных
5. **idempotent**: event_fingerprint, batch external_batch_key
6. **explainable**: decision_explanation (rule_code + weight + message + payload)

### Поток данных (не менять)

```
Import → Recognition → Event → Snapshot → Decision → (future Ledger)
```

---

## 2. Разрешено менять в фазах 2+

| Можно | Нельзя |
|-------|--------|
| ✏️ Rule implementations (код правил) | ❌ Таблицы ядра |
| ✏️ Ruleset versions | ❌ Статусные модели / enums |
| ✏️ Queue topology (очереди, workers pool) | ❌ Версионность (version, superseded) |
| ✏️ Workers (количество, параметры) | ❌ Replay контракт |
| ✏️ Observability (метрики, алерты, логи) | ❌ snapshot-only invariant |
| ✏️ API endpoints (CRUD) | ❌ Поток (flow) |
| ✏️ UI | ❌ Формула Decision = f(…) |

---

## 3. Gate перед Phase 2

### Data Gate

- [ ] повторный импорт не создаёт событие (fingerprint)
- [ ] replay даёт идентичный результат
- [ ] смена ruleset создаёт новую decision
- [ ] correction не меняет старые версии
- [ ] snapshot воспроизводим

### Performance Gate

- [ ] импорт 100k транзакций
- [ ] пересчёт 10k событий
- [ ] explain запрос < 200 ms
- [ ] replay batch < 15 мин

### Operations Gate

- [ ] dead letter queue
- [ ] ручной reprocess (manual retry)
- [ ] trace_id через весь pipeline
- [ ] audit по decision (actor_id, timestamp, diff)

---

## 4. Условие старта Ledger (фаза 3)

Не начинать Ledger до появления полного end-to-end сценария:

```
bank file → document → event → snapshot → decision → review UI → replay
```

---

## 5. Что будет в Phase 2

| Модуль | Описание |
|--------|----------|
| Queue / Orchestration | Workers pool, state transitions (NEW → ... → DONE/FAILED) |
| Workers | Recognition worker + Decision worker |
| Rule Runtime | Rule interface, registry, priority chain |
| Replay execution | ReplayService.recalculate() |
| API | GET events, POST replay, PATCH decision |
| Observability | trace_id, DLQ, audit log |
| Нагрузочный сценарий | 100k импорт, 10k пересчёт, explain < 200ms |

---

## 6. Команды для проверки freeze

```sql
-- 1. Статусы не менялись
SELECT typname, enumlabel
FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid
WHERE t.typnamespace = 'accounting'::regnamespace
ORDER BY typname, enumlabel;

-- 2. Таблицы ядра не менялись
SELECT tablename FROM pg_tables WHERE schemaname = 'accounting'
ORDER BY tablename;

-- 3. UNIQUE constraints на месте
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'accounting.accounting_event'::regclass
AND contype = 'u';
```
