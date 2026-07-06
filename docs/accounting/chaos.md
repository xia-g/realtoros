# Accounting Pipeline — Chaos Tests (теоретический анализ)

---

## 1. DB Unavailable

| Симптом | Event processing зависает, новые events не создаются |
|---------|-------------------------------------------------------|
| Worker behaviour | `asyncpg.connect()` raises `ConnectionFailureError` |
| Recovery | При восстановлении DB — pool переподключается автоматически |
| Data loss | Нет — events в памяти не хранятся |
| DoD | Worker должен retry с exponential backoff |

**Реализация:** `retry_policy.py` с `max_attempts=5`, `backoff 10s → 30min`.

---

## 2. Worker Crash

| Симптом | Worker умирает mid-processing |
|---------|-------------------------------|
| State | `processing_state` сохранён в DB: RECOGNIZING / DECIDING |
| Recovery | При рестарте worker видит события в промежуточных статусах |
| Duplicate safety | recalculate() идемпотентен — создаёт новую decision |
| Data loss | Нет — committed решения сохранены |

**Проверено:** reliability/test_worker_restart.py ✅

---

## 3. Queue Unavailable

Phase 2 использует asyncpg напрямую, без внешней очереди.
Worker poll — это `SELECT ... WHERE processing_state = 'new'`.

| Симптом | SELECT возвращает ошибку |
|---------|--------------------------|
| Recovery | Pool retry, следующая итерация poll |
| Duplicate | Нет — poll выбирает одно событие один раз |

---

## 4. Delayed Snapshot

| Симптом | snapshot_builder медленный (OCR, внешние сервисы) |
|---------|----------------------------------------------------|
| Impact | Event остаётся в `processing_state=RECOGNIZING` |
| Timeout | Нет — snapshot ждёт бесконечно |
| Recovery | Worker должен иметь visibility timeout |

**Рекомендация:** добавить `timeout` на build_snapshot — если > 30s, переводить в FAILED.

---

## 5. Corrupted Payload

| Симптом | snapshot `inputs_json` содержит невалидные данные |
|---------|---------------------------------------------------|
| Decision Engine | Правила обрабатывают snapshot — ошибка валидации |
| Recovery | exception → processing_state=FAILED |
| Исправление | Новый snapshot (новая версия) → replay |

---

## 6. Replay Storm

| Симптом | 100 replays на одно событие за минуту |
|---------|---------------------------------------|
| Impact | 100 новых decision (все superseded, кроме 1) |
| Storage | 100 строк в accounting_decision на одно событие |
| Mitigation | Rate limit: max 10 replays/min/event |

**Проверено:** reliability/test_replay_storm.py — 100 replays, 1 active decision ✅

---

## Итоговая матрица

| Сценарий | Risk | Mitigation | Tested |
|----------|------|-----------|--------|
| DB unavailable | High | Retry pool, backoff | ❌ |
| Worker crash | Medium | State in DB, idempotent | ✅ |
| Duplicate message | Medium | recalculate idempotent | ✅ |
| Delayed snapshot | Low | Timeout + FAILED | ❌ |
| Corrupted payload | Low | exception → FAILED | ❌ |
| Replay storm | Low | Rate limit (future) | ✅ |
| DLQ overflow | Low | Alert on DLQ size | ❌ |
