# Accounting Pipeline — Security

---

## 1. Tenant Isolation

Все сущности содержат `company_id`. Каждый запрос должен проверять принадлежность компании.

| Таблица | Tenant field |
|---------|-------------|
| accounting_event | `company_id` |
| accounting_batch | `company_id` |
| tax_regime | `company_id` |
| tax_period | `company_id` |

**Принцип:** ни один API запрос не должен возвращать данные другой компании без явной фильтрации по `company_id`.

---

## 2. Batch Isolation

- Batch принадлежит одной компании (`company_id`).
- События могут быть созданы только в рамках batch.
- События разных компаний не могут быть в одном batch.

---

## 3. Replay Authorization

Replay — деструктивная операция (создаёт новую decision).

Требования:
- POST `/api/v1/accounting/replay` — только роль `accountant`, `admin`
- GET `/api/v1/accounting/events` — любая аутентифицированная роль
- POST `/api/v1/accounting/dlq/{id}/reprocess` — только `admin`

**Текущий статус:** авторизация не реализована (Phase 2 scope не включает auth middleware).

---

## 4. Audit Integrity

| Действие | Логируется | Actor |
|----------|-----------|-------|
| Decision created | ✅ structured log | system |
| Decision superseded | ✅ structured log | system |
| Manual override | ⬜ будущая фаза | user |
| DLQ reprocess | ✅ structured log | admin |

---

## 5. API Throttling

Рекомендуемые лимиты (не реализованы в Phase 2):

| Endpoint | Rate limit | Reason |
|----------|-----------|--------|
| `POST /replay` | 10/min/user | Replay — тяжёлая операция |
| `POST /dlq/{id}/reprocess` | 5/min/user | Административное действие |
| `GET /events` | 100/min/user | Стандартный |

---

## 6. Input Validation

| Поле | Валидация |
|------|-----------|
| event_id | UUID format |
| batch_id | UUID format |
| company_id | UUID format |
| amount | NUMERIC(16,2), > 0 |
| event_type | Допустимые значения enum |
| source_system | BANK, DOCS, CRM, MANUAL |

---

## 7. Risks

| Риск | Воздействие | Митигация |
|------|------------|-----------|
| Replay без авторизации | Неконтролируемое создание decision | Добавить auth middleware в Phase 3 |
| Отсутствие tenant filter | Утечка данных между компаниями | Проверять company_id во всех endpoints |
| Snapshot подмена | Decision ≠ f(Event, Snapshot) | snapshot immutable после создания |
