# Accounting Core — Архитектурное решение

**Дата:** 2026-06-15
**Статус:** ❄️ **FINAL — Architecture Freeze** (v5)
**Версия:** 5.0.0

---

## 1. Контекст и цель

Платформа Real Estate OS содержит модули CRM, документооборота, банковского импорта.
Для перехода к полноценному бухгалтерскому учёту необходим отдельный bounded context **ACCOUNTING**.

Цель: построить надёжное бухгалтерское ядро, которое:
- не зависит напрямую от CRM и документов;
- обрабатывает финансовые потоки через промежуточный слой хозяйственных событий (Accounting Event Journal);
- поддерживает несколько налоговых режимов;
- допускает версионные исправления;
- поддерживает deferred processing (асинхронную очередь правил);
- обеспечивает объяснимость решений (decision_explanation + recognition_snapshot);
- защищает от дублей (event_fingerprint);
- гарантирует **воспроизводимость** пересчёта (Rule Engine читает ТОЛЬКО снимки).

---

## 2. Архитектурный поток

```
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│ Bank Transactions│ ──▶ │ Accounting Event     │ ──▶ │ Ledger           │
│ Documents       │ ──▶ │ Journal              │     │ (фаза 3)         │
│ Business Rules  │ ──▶ │                      │     │                  │
└─────────────────┘     └──────────┬───────────┘     └────────┬─────────┘
                                   │                           │
                                   ▼                           ▼
                            ┌──────────────┐         ┌──────────────────┐
                            │ Rule Engine   │         │ Tax Registers    │
                            │ (только       │         │ (фаза 4)         │
                            │  снимки!)     │         └──────────────────┘
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────────┐
                            │ recognition_     │
                            │ snapshot         │
                            │ + tax_regime     │
                            │   snapshot       │
                            └──────────────────┘
```

### Принципы (v5 — final)

1. **Никаких прямых связей** между bank_transaction и ledger_entry.
2. **Accounting Event Journal** — единственный входной канал в учёт.
3. Все внешние модули интегрируются через `(source_system, source_type, source_id)`.
4. Событие **версионно** — исправление = новая версия, старая помечается `is_current=false`.
5. **accounting_batch** группирует события с идемпотентностью.
6. **event_fingerprint** — защита от дублей.
7. **recognition_snapshot** — фиксация входных данных (воспроизводимость).
8. **Rule Engine читает ТОЛЬКО снимки** — никогда живые данные.
9. **ruleset_version** — версия правил, отдельно от версии решения.
10. **Replay API** — пересчёт без Ledger.

---

## 3. Доменная модель

### 3.1. company
Уже существует. В accounting FK.

### 3.2. tax_regime
Налоговый режим компании. Непересекающиеся по датам.

### 3.3. tax_period
OPEN → LOCKED → CLOSED.

### 3.4. accounting_event (центральная сущность)

Типы: BANK_INFLOW, BANK_OUTFLOW, SALE, PURCHASE, CLIENT_PAYMENT, AGENT_COMMISSION, REFUND, TRANSFER, MANUAL.

**Поля:**
- source_system | source_type | source_id | event_fingerprint
- version | superseded_by | superseded_reason | is_current
- current_decision_id | decision_state
- processing_state | next_retry_at | attempt_count | last_error

---

## 4. Дополнительные сущности

### 4.1. accounting_decision

| Поле | Описание |
|------|----------|
| event_id | FK → accounting_event |
| decision_version | Номер решения (1, 2, …) |
| **ruleset_version** | Версия правил (например, `2026.06.15`) |
| policy_version | Внутренняя версия политики |
| included | BOOLEAN |
| reason | TEXT |
| manual_override | BOOLEAN |
| superseded_at | TIMESTAMPTZ |

Уникальность: `UNIQUE(event_id) WHERE superseded_at IS NULL`

### 4.2. decision_explanation
Детализация каждого правила.

### 4.3. recognition_snapshot
Immutable слепок. Содержит:
- documents (извлечённые данные, не сырые файлы)
- transactions (из банковского импорта)
- tax_regime (режим компании на дату события)

### 4.4. event_transaction / event_document
Связи с внешними модулями (только FK, не для чтения Engine).

---

## 5. Критический инвариант ❗

### Rule Engine читает ТОЛЬКО снимки

```
ДОПУСТИМО:                         ЗАПРЕЩЕНО:
┌────────────────────┐             ┌────────────────────┐
│ accounting_event   │             │ document           │
│ recognition_       │             │ bank_transaction   │
│   snapshot         │             │ crm_deal           │
│ tax_regime         │             │ companies          │
│ (только через      │             │ users              │
│  snapshot)         │             │ ...                │
└────────────────────┘             └────────────────────┘
```

**Формула воспроизводимости:**
```
Decision = f(Event, Snapshot, RulesetVersion)
```

**Почему:** без этого правила пересчёт через 6 месяцев даст другой результат (документ мог измениться, транзакция удалиться).

**Исключение:** manual_override всегда возможен (человек важнее автомата).

### ruleset_version

При пересчёте:
```sql
new_decision_version = old_decision_version + 1
new_ruleset_version  = '2026.06.15'  -- или актуальная
```

Позволяет ответить на вопрос: «почему вчера включалось, а сегодня исключается?»

---

## 6. Rule Engine (модуль)

### Контракт

```python
class Rule:
    rule_code: str
    priority: int

    def supports(event: accounting_event) -> bool: ...
    def evaluate(event, snapshot, tax_regime_snapshot) -> RuleResult: ...

class DecisionEngine:
    def evaluate(event, snapshot, tax_regime_snapshot, ruleset_version) -> Decision:
        applicable = ...
        results = ...
        return Decision.aggregate(results, ruleset_version)
```

### ReplayService

Сервисный контракт (не таблица):

```python
class ReplayService:
    def recalculate(event_id, snapshot_version, ruleset_version) -> ReplayResult:
        # 1. Загрузить accounting_event
        # 2. Загрузить recognition_snapshot (указанной версии)
        # 3. Применить DecisionEngine
        # 4. Сохранить новую accounting_decision (decision_version+1)
        # 5. Вернуть diff: старый included → новый included
```

```python
class ReplayResult:
    new_decision_id: UUID
    old_included: bool
    new_included: bool
    diff: list[str]  # какие правила изменили решение
```

Используется:
- обновили OCR → пересчёт события;
- обновили правило УСН → массовый пересчёт;
- бухгалтер запросил «а что если».

---

## 7. Инварианты (окончательный список)

1. **versioned correction**: UPDATE запрещён — исправление = новая версия.
2. **unique source**: `(source_system, source_type, source_id, event_type)` + `is_current` → UNIQUE.
3. **event_fingerprint**: `(company_id, event_fingerprint, is_current)` → UNIQUE.
4. **batch idempotency**: `external_batch_key` → UNIQUE.
5. **non-overlapping regimes**: tax_regime.
6. **one active decision**: UNIQUE(event_id) WHERE superseded_at IS NULL.
7. **snapshot-only Rule Engine**: Engine читает только accounting_event + снимки.
8. **воспроизводимость**: Decision = f(Event, Snapshot, RulesetVersion).
9. **audit trail**: каждое изменение логируется (actor_id, timestamp).

---

## 8. Lifecycle (final)

```
Batch (import)
    │
    ▼
NEW ──→ RECOGNIZING ──→ READY_FOR_DECISION ──→ DECIDING ──→ DONE
                              │                      │
                              └──→ FAILED ───────────┘
                                            │
                                       retry (next_retry_at)
```

DONE:
- decision_state = INCLUDED → CONFIRMED → Ledger
- decision_state = EXCLUDED → review (опционально)
- decision_state = REVIEW_REQUIRED → manual

---

## 9. Партиционирование

accounting_event — RANGE(event_date), on-demand.

---

## 10. Architecture Freeze ❄️

### Стабильно (не трогать)

**Домен:**
- accounting_event, accounting_decision, decision_explanation, recognition_snapshot
- accounting_batch, tax_regime, tax_period, event_transaction, event_document
- статусные модели (processing_state, decision_state, recognition_status)

**Инварианты:**
- `Decision = f(Event, Snapshot, RulesetVersion)`
- immutable, versioned, replayable, idempotent, explainable

**Поток:**
```
Import → Recognition → Event → Snapshot → Decision → (future Ledger)
```

### Разрешено менять в фазах 2+

| Можно | Нельзя |
|-------|--------|
| Rule implementations | Таблицы ядра |
| Ruleset versions | Статусы / enums |
| Queue topology | Версионность |
| Workers | Replay контракт |
| Observability | snapshot-only invariant |
| API / UI | Поток (flow) |

---

## 11. Phase 2 — Recognition + Decision Engine (plan)

### Scope

| Модуль | Описание |
|--------|----------|
| **Queue / Orchestration** | Workers pool, state transitions (NEW → RECOGNIZING → READY_FOR_DECISION → DECIDING → DONE/FAILED) |
| **Workers** | Recognition worker + Decision worker (consumers of processing queue) |
| **Rule Runtime** | Rule interface, registry, priority chain, aggregation logic |
| **Replay execution** | ReplayService.recalculate() — по одному событию и batch |
| **API** | GET events with filters, POST replay, PATCH decision override |
| **Observability** | trace_id, dead letter queue, audit log |
| **Нагрузочный сценарий** | 100k импорт, 10k пересчёт, explain < 200ms |

### Gate перед стартом Phase 2

**Data Gate:**
- [ ] повторный импорт не создаёт событие (fingerprint)
- [ ] replay даёт идентичный результат
- [ ] смена ruleset создаёт новую decision
- [ ] correction не меняет старые версии
- [ ] snapshot воспроизводим

**Performance Gate:**
- [ ] импорт 100k транзакций
- [ ] пересчёт 10k событий
- [ ] explain запрос < 200 ms
- [ ] replay batch < 15 мин

**Operations Gate:**
- [ ] dead letter queue
- [ ] ручной reprocess
- [ ] trace_id через весь pipeline
- [ ] audit по decision

### Не начинать Ledger до

Первый end-to-end сценарий:

```
bank file → document → event → snapshot → decision → review UI → replay
```

---

## 12. Roadmap (final)

| Фаза | Что | Критерий готовности |
|------|-----|---------------------|
| **1** (текущая) | ✅ **Architecture Freeze** | См. ниже |
| **2** | Recognition + Decision Engine | Импорт банка → событие → snapshot → решение (explainable). Решение: included/excluded/review_required. Replay даёт тот же результат при тех же данных. |
| **3** | Ledger | Проводки, план счетов |
| **4** | Tax Registers | КУДиР, книги покупок/продаж |
| **5** | Reconciliation | Сверка |
| **6** | API / UI | |

### Критерий готовности фазы 1 (Core)

**Functional:**
- [x] импорт банка создаёт batch
- [x] документы связываются через event_document
- [x] создаётся accounting_event
- [x] создаётся recognition_snapshot
- [x] Rule Engine выдаёт решение (accounting_decision + decision_explanation)
- [x] решение объяснимо (weight, message, payload_json)
- [x] событие пересчитывается (ReplayService)
- [x] дубликат банка отклоняется (event_fingerprint)

**Non-functional:**
- [x] идемпотентность (batch key, fingerprint)
- [x] воспроизводимость (snapshot-only engine)
- [x] версионность (version, superseded_by, decision_version)
- [x] audit trail (actor_id, manual_override, superseded_reason)
- [x] отсутствие mutable state (immutable после версии)
