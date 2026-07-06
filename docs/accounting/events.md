# Accounting Core — Интеграционные события (v2)

**Версия:** 2.0.0

---

## 1. Доменные события (Domain Events)

Все события публикуются через `DomainEventBus` (существующий механизм в проекте).

| Событие | Триггер | Payload |
|---------|---------|---------|
| `accounting_event.created` | INSERT в accounting_event | `{event_id, company_id, batch_id, event_type, amount, currency, event_date, source_system}` |
| `accounting_event.recognized` | INSERT в accounting_decision (superseded_at IS NULL) | `{event_id, decision_id, included, policy_version, decision_version}` |
| `accounting_event.confirmed` | UPDATE recognition_status → 'confirmed' | `{event_id, actor_id, company_id}` |
| `accounting_event.superseded` | UPDATE is_current=false + ссылка на новую версию | `{original_id, new_id, reason, actor_id}` |
| `accounting_batch.started` | INSERT в batch (status=processing) | `{batch_id, company_id, source}` |
| `accounting_batch.completed` | UPDATE status → completed | `{batch_id, company_id, source, events_count}` |
| `accounting_batch.failed` | UPDATE status → failed | `{batch_id, company_id, error}` |
| `tax_regime.changed` | INSERT/UPDATE tax_regime | `{company_id, regime_type, valid_from, is_active}` |
| `tax_period.opened` | INSERT tax_period | `{period_id, company_id, period_type, date_from, date_to}` |
| `tax_period.locked` | UPDATE status → 'locked' | `{period_id, company_id, date_to}` |
| `tax_period.closed` | UPDATE status → 'closed' | `{period_id, company_id, date_to}` |

---

## 2. Формат события

```json
{
  "event_type": "accounting_event.created",
  "version": 1,
  "timestamp": "2026-06-15T10:00:00Z",
  "correlation_id": "uuid",
  "actor_id": "uuid",
  "entity_type": "accounting_event",
  "entity_id": "uuid",
  "payload": {
    "event_id": "uuid",
    "company_id": "uuid",
    "batch_id": "uuid",
    "event_type": "bank_inflow",
    "amount": 150000.00,
    "currency": "RUB",
    "source_system": "BANK",
    "event_date": "2026-06-15T09:30:00Z"
  }
}
```

---

## 3. Подписчики событий

### Планируемые обработчики

| Событие | Обработчик | Действие | Фаза |
|---------|-----------|----------|------|
| `accounting_event.created` | rule_engine | Применить правила → accounting_decision | 2 |
| `accounting_event.recognized` | ledger_handler | Создать проводки | 3 |
| `accounting_event.recognized` | tax_handler | Расчёт налогов | 4 |
| `accounting_event.superseded` | ledger_handler | Сторно старых проводок, создание новых | 3 |
| `accounting_batch.completed` | notification | Оповестить пользователя | 6 |
| `tax_period.closed` | report_generator | Генерация отчёта | 4 |

### Текущий event bus (уже в проекте)

- `register_sync_handlers()` — регистрация в `main.py` lifespan.

---

## 4. Интеграция с внешними модулями

### 4.1. Bank Import

```
1. bank_transaction.imported
2. batch = accounting_batch.create(source='bank_import_20260615')
3. event = accounting_event.create(
       source_system='BANK',
       source_type='transaction',
       source_id=transaction_id,
       event_type=bank_inflow|bank_outflow,
       batch_id=batch.id
   )
4. event_transaction.create(event.id, transaction_id, 'auto')
5. batch.complete()
```

### 4.2. Documents

```
1. document.validated (OCR complete)
2. batch = accounting_batch.create(source='doc_import_...')
3. event = accounting_event.create(
       source_system='DOCS',
       source_type='invoice',
       source_id=document_id,
       event_type=sale|purchase|agent_commission,
       batch_id=batch.id
   )
4. event_document.create(event.id, document_id, 'primary')
5. batch.complete()
```

### 4.3. CRM Deals

```
1. deal.closed
2. batch = accounting_batch.create(source='crm_deal_...')
3. event = accounting_event.create(
       source_system='CRM',
       source_type='deal',
       source_id=deal_id,
       event_type=client_payment|agent_commission,
       batch_id=batch.id
   )
4. batch.complete()
```

### 4.4. Manual (UI)

```
1. batch = accounting_batch.create(source='manual_entry', status='completed')
2. event = accounting_event.create(
       source_system='MANUAL',
       source_type='user',
       source_id='manual_{uuid}',
       requires_review=true,
       batch_id=batch.id
   )
```

---

## 5. API точки интеграции

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/accounting/events` | Создать событие (с проверкой source) |
| POST | `/api/v1/accounting/events/{id}/supersede` | Создать новую версию события |
| GET | `/api/v1/accounting/events` | Список (только is_current=true) |
| GET | `/api/v1/accounting/events/{id}` | Детали + история версий |
| POST | `/api/v1/accounting/events/{id}/recognize` | Применить правила |
| POST | `/api/v1/accounting/events/{id}/confirm` | Подтвердить |
| POST | `/api/v1/accounting/events/{id}/reject` | Отклонить |
| POST | `/api/v1/accounting/batches` | Создать batch |
| GET | `/api/v1/accounting/batches/{id}` | Batch + его события |
| GET | `/api/v1/accounting/decisions` | Список решений |
| GET | `/api/v1/accounting/regimes` | Налоговые режимы |
| GET | `/api/v1/accounting/periods` | Фискальные периоды |
| POST | `/api/v1/accounting/periods/{id}/close` | Закрыть период |

---

## 6. Схема запроса на создание события

```json
POST /api/v1/accounting/events
{
  "company_id": "uuid",
  "batch_id": "uuid",
  "event_type": "bank_inflow",
  "event_date": "2026-06-15T10:00:00Z",
  "amount": 150000.00,
  "currency": "RUB",
  "source_system": "BANK",
  "source_type": "transaction",
  "source_id": "uuid",
  "counterparty_id": "uuid",
  "description": "Оплата по договору №123",
  "is_tax_relevant": true
}
```

**Ответ:**
```json
{
  "id": "uuid",
  "version": 1,
  "is_current": true,
  "event_type": "bank_inflow",
  "recognition_status": "pending"
}
```
