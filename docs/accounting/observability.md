# Accounting Pipeline — Observability

---

## 1. Trace ID

Каждый запрос в pipeline получает `trace_id`:

```
trace_id: uuid_v4
```

Распространяется через:
- `backend/accounting/tracing/tracer.py` — `set_trace_id()` / `get_trace_id()`
- ContextVar (async-safe)

### Correlation

| Entity | Field |
|--------|-------|
| Event | `id` |
| Batch | `id` |
| Decision | `id` |
| Snapshot | `id` |
| Trace | `trace_id` |

Все метрики и логи содержат `trace_id`, `event_id`, `batch_id`.

---

## 2. Метрики

| Метрика | Тип | Labels | Источник |
|---------|-----|--------|----------|
| `event_processing_seconds` | Timer | stage={recognition,recognition_replayed} | recognition_worker |
| `decision_duration_seconds` | Timer | status={success,failed} | decision_worker |
| `replay_duration_seconds` | Timer | status={success,failed} | replay/service |
| `decision_count` | Counter | decision_state | replay/service |
| `retry_count` | Counter | — | orchestrator |

### Доступ

```http
GET /api/v1/accounting/metrics
```

Ответ:
```json
{
  "timers": {
    "decision_duration_seconds": {
      "_total": {"count": 34, "avg": 0.028, "min": 0.015, "max": 0.065}
    }
  },
  "counters": {
    "decision_count": 34
  }
}
```

---

## 3. Dashboards (текстовые)

### Decision Throughput

```ascii
Events/s: ████████░░ 80/s
P95:      ███░░░░░░░ 35ms
Errors:   ░░░░░░░░░░ 0
```

### DLQ Size

```ascii
DLQ: ░░░░░░░░░░ 0 events
```

### Retry Rate

```ascii
Retries: ░░░░░░░░░░ 0 (last hour)
```

---

## 4. Мониторинг

| Что проверять | Как | Период |
|---------------|-----|--------|
| Processing queue depth | `GET /api/v1/accounting/events?processing_state=new` | 5 min |
| DLQ | `GET /api/v1/accounting/dlq` | 15 min |
| Failed events | `GET /api/v1/accounting/events?processing_state=failed` | 5 min |
| Metrics | `GET /api/v1/accounting/metrics` | 1 min |
| Replay consistency | e2e test | 1 hour |

---

## 5. Логирование

Структурированные логи (через logging.Logger):

```json
{"event": "decision_created", "event_id": "...", "decision_id": "...",
 "included": true, "ruleset": "2026.06.15", "trace_id": "..."}
```

### Ключевые логи

| Событие | Logger | Fields |
|---------|--------|--------|
| snapshot_built | accounting.worker.recognition | event_id, snapshot_version |
| decision_created | accounting.worker.decision | event_id, decision_id, included, ruleset |
| replay_completed | accounting.worker.replay | event_id, old_included, new_included, diff |
| audit | accounting.audit | event_id, decision_id, action, actor_id |
