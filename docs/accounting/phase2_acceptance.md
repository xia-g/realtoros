# Phase 2 — Recognition + Decision Engine

**Дата:** 2026-06-15
**Статус:** План
**Артефакт:** Контракт выполнения (не часть ядра)

---

## 1. E2E сценарий (обязательный)

```
1. upload bank file
2. → create batch
3. → create accounting_event
4. → create recognition_snapshot
5. → execute Rule Engine
6. → create accounting_decision
7. → generate explanations (decision_explanation)
8. → show review list
9. → replay event
10. → verify deterministic result
```

### Критерий

- ❌ ни одного ручного SQL
- ❌ ни одного прямого UPDATE события
- ✅ повторный запуск идемпотентен
- ✅ replay даёт идентичный результат

---

## 2. SLO (первые целевые значения)

| Метрика | Цель | Измерение |
|---------|------|-----------|
| **Import latency** P95 | < 5 мин / 100k tx | от загрузки файла до создания events |
| **Decision latency** P95 | < 1 сек / event | от READY_FOR_DECISION до DONE |
| **Replay latency** P95 | < 3 сек / event | от запроса replay до новой decision |
| **Duplicate rejection** | > 99.99% | fingerprint + batch key |
| **Replay consistency** | = 100% | одинаковый input → одинаковый output |
| **Decision explainability** | = 100% | каждое решение имеет explanations |
| **Snapshot coverage** | = 100% | каждое событие имеет snapshot до decision |

---

## 3. Failure matrix

| Ситуация | Реакция | Processing state | Decision state |
|----------|---------|-----------------|----------------|
| OCR timeout | retry (attempt_count++, next_retry_at) | `FAILED` | (без изменений) |
| Rule exception | FAILED, manual reprocess | `FAILED` | (без изменений) |
| Missing document | REVIEW_REQUIRED | `DONE` | `REVIEW_REQUIRED` |
| Duplicate batch | ignore (external_batch_key) | — | — |
| Duplicate event | ignore (event_fingerprint) | — | — |
| Snapshot mismatch | hard fail | `FAILED` | (без изменений) |
| Manual override | new decision_version | (без изменений) | (зависит) |

### Retry policy (default)

| Параметр | Значение |
|----------|----------|
| max_attempts | 5 |
| initial_backoff | 10 sec |
| backoff_multiplier | 2.0 |
| max_backoff | 30 min |
| dead_letter_after | 5 failures |

---

## 4. Definition of Done для Phase 2

### Functional

- [ ] импорт банка (batch → events)
- [ ] импорт документов (event_document связи)
- [ ] recognition_snapshot создаётся до решения
- [ ] решение создаётся (accounting_decision)
- [ ] объяснение отображается (decision_explanation)
- [ ] replay воспроизводим (ReplayService)
- [ ] UI показывает review list (decision_state filter)
- [ ] ручной override работает

### Reliability

- [ ] очередь переживает рестарт (processing_state сохраняется)
- [ ] worker идемпотентен (повторный запуск не создаёт дублей)
- [ ] нет двойных решений (uq_decision_active)
- [ ] дубликаты отклоняются (fingerprint, batch key)
- [ ] FAILED события попадают в DLQ / retry queue

### Observability

- [ ] trace_id через весь pipeline (event → decision → replay)
- [ ] metrics: latency P95, throughput, error rate
- [ ] audit: каждое изменение decision логируется
- [ ] alert: retry count превышен, DLQ не пуста
- [ ] health endpoint: очередь, workers, ошибки

---

## 5. Что НЕ входит в Phase 2

| Компонент | Фаза |
|-----------|------|
| Ledger / проводки | 3 |
| План счетов | 3 |
| Tax registers (КУДиР) | 4 |
| Reconciliation / сверка | 5 |
| Отчёты (P&L, Balance) | 5 |
| UI для Ledger | 6 |

---

## 6. Условие перехода к Phase 3 (Ledger)

Не начинать, пока не пройдёт полный E2E:

```
bank file → document → event → snapshot → decision → review UI → replay
```

Все SLO подтверждены нагрузочным тестированием.
