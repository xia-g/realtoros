# Phase 3 — Ledger Acceptance Criteria

**Дата:** 2026-06-15
**Статус:** План
**Артефакт:** Контракт выполнения (не часть freeze)

---

## 1. Functional

### 1.1. Decision → Posting

```
decision (included=true)
  → ledger_entry
  → ledger_line (debit = credit)
```

**Критерий:**
- [ ] Каждое INCLUDED решение создаёт ровно одну проводку
- [ ] Сумма дебетов = Сумма кредитов (double-entry invariant)
- [ ] EXCLUDED решения не создают проводок
- [ ] Проводка содержит `posting_decision_link` → original decision

### 1.2. Posting → Ledger

```
ledger_entry
  → chart_of_accounts check (account exists, is active)
  → period check (period is OPEN or current)
  → ledger_line INSERT
  → posting_decision_link INSERT
```

**Критерий:**
- [ ] Проводка проходит валидацию счетов
- [ ] Несуществующий счёт → reject
- [ ] Закрытый период → reject (или delta posting)

### 1.3. Reversal

```
original: DR 62 100 / CR 90 100
reversal: DR 90 100 / CR 62 100  (is_reversal=true, reversed_entry_id=original)
```

**Критерий:**
- [ ] Сторно обнуляет оригинал
- [ ] `reversed_entry_id` указывает на оригинал
- [ ] Повторное сторно того же оригинала → reject (уже сторнировано)

### 1.4. Delta Posting (closed period)

```
Закрытый период Q1:
  old_amount=100, new_amount=120
  → delta=20, posting в текущий открытый период Q2
```

**Критерий:**
- [ ] Закрытый период не получает новых проводок
- [ ] Delta = abs(new − old)
- [ ] В `description` указано: "Correction for period Q1"
- [ ] Трассируемо до original decision

---

## 2. Performance

| Метрика | Цель | Измерение |
|---------|------|-----------|
| Posting throughput | > 500 evt/s | 10k postings |
| Posting latency P95 | < 200 ms | от submit до INSERT |
| Reversal latency P95 | < 300 ms | reversal + new posting |
| Delta posting latency P95 | < 300 ms | период check + delta |

---

## 3. Reliability

| Требование | Критерий |
|-----------|----------|
| No double posting | Повторный replay не дублирует проводки (идентифицируется по decision_version) |
| Idempotent replay | Replay того же решения → проводка не создаётся повторно |
| Reversal idempotent | Повторное сторно → reject |
| Period lock consistency | CLOSED → никаких INSERT, кроме delta |
| Immutable guarantee | UPDATE/DELETE запрещены на уровне БД |

---

## 4. Operations

| Сценарий | Действие | Ожидание |
|----------|----------|----------|
| Close period | POST /api/v1/accounting/periods/{id}/close | period status → CLOSED |
| Open period | POST /api/v1/accounting/periods/{id}/open | period status → OPEN |
| Reversal | POST /api/v1/accounting/ledger/{entry_id}/reverse | new reversal entry |
| Recovery after crash | Worker restart | Незавершённые postings восстанавливаются (processing_state) |

---

## 5. E2E сценарий

```
1. INCLUDED decision → posting (DR/CR check)
2. EXCLUDED decision → no posting
3. Reversal → correct accounts
4. Replay in open period → new posting, old immutable
5. Replay in closed period → delta posting
6. Double replay → idempotent
7. Period close → reject new postings
```

---

## 6. Что НЕ входит в Phase 3

| Компонент | Фаза |
|-----------|------|
| Tax registers | 4 |
| KUDIR | 4 |
| Report generation | 5 |
| AI Audit | 5 |
| Reconciliation | 6 |
| UI | 7 |
