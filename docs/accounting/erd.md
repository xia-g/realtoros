# Accounting Core — ERD (v4)

---

## 1. Сводная ERD

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          accounting schema                                │
│                                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐    │
│  │  company     │    │ tax_regime   │    │ tax_period               │    │
│  │  (сущ.)      │──1:N              │    │                          │    │
│  └──────────────┘    └──────────────┘    └──────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │   accounting_batch                                               │    │
│  │   id, company_id, source, external_batch_key (UNIQUE), checksum  │    │
│  │   status, started_at, completed_at                               │    │
│  └──────────────────────────┬───────────────────────────────────────┘    │
│                             │ 1:N                                        │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │   accounting_event  (Accounting Event Journal)                   │    │
│  │   партиц. по месяцам                                             │    │
│  │                                                                   │    │
│  │   source_system | source_type | source_id                         │    │
│  │   event_fingerprint VARCHAR(64)  ←─ UNIQUE(company_id, fp, curr)  │    │
│  │   version | superseded_by | superseded_reason | is_current        │    │
│  │   decision_state: PENDING / INCLUDED / EXCLUDED / REVIEW_REQUIRED │    │
│  │   processing_state: NEW / RECOGNIZING / READY_FOR_DECISION       │    │
│  │                    / DECIDING / DONE / FAILED                     │    │
│  │   next_retry_at | attempt_count | last_error                      │    │
│  └──────────────────────┬──────────────────────────────────────────┘    │
│                         │                                                │
│            1:N          │        1:1 (акт.)                              │
│                         ▼                                                │
│  ┌─────────────────────────────────┐  ┌────────────┐                   │
│  │  accounting_decision            │  │ decision_  │                   │
│  │  event_id, decision_version     │  │ explanation │                   │
│  │  policy_version, included       │  │             │                   │
│  │  superseded_at                  │  │ rule_code   │                   │
│  └─────────────┬───────────────────┘  │ weight      │                   │
│                │                      │ message     │                   │
│                │ 1:N                  │ payload_json│                   │
│                ▼                      └─────────────┘                   │
│  ┌─────────────────────────────────┐                                    │
│  │  recognition_snapshot           │                                    │
│  │  event_id, snapshot_version     │                                    │
│  │  inputs_json (JSONB)            │                                    │
│  │  created_at                     │                                    │
│  └─────────────────────────────────┘                                    │
│                                                                           │
│  ┌──────────────────────┐  ┌──────────────────────┐                    │
│  │  event_transaction   │  │  event_document      │                    │
│  │  event_id | txn_id   │  │  event_id | doc_id   │                    │
│  │  match_type, conf    │  │  role, added_at      │                    │
│  └──────────────────────┘  └──────────────────────┘                    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Сущности (детально)

### 2.1. accounting_event (v4)

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID PK | |
| company_id | UUID FK | |
| batch_id | UUID FK | |
| event_type | event_type enum | |
| event_date | TIMESTAMPTZ | |
| amount | NUMERIC(16,2) | |
| currency | CHAR(3) | |
| source_system | VARCHAR(20) | BANK, DOCS, CRM, MANUAL |
| source_type | VARCHAR(30) | |
| source_id | VARCHAR(64) | |
| **event_fingerprint** | VARCHAR(64) | SHA256(company_id + source_system + source_id + amount + event_date) |
| counterparty_id | UUID NULL | |
| recognition_status | recognition_status enum | |
| is_tax_relevant | BOOLEAN | |
| requires_review | BOOLEAN | |
| description | TEXT | |
| version | INTEGER DEFAULT 1 | |
| superseded_by | UUID NULL | |
| superseded_reason | superseded_reason enum NULL | |
| is_current | BOOLEAN DEFAULT true | |
| current_decision_id | UUID NULL | |
| **decision_state** | decision_state enum | PENDING, INCLUDED, EXCLUDED, REVIEW_REQUIRED |
| **processing_state** | processing_state enum | NEW, RECOGNIZING, READY_FOR_DECISION, DECIDING, DONE, FAILED |
| next_retry_at | TIMESTAMPTZ NULL | |
| attempt_count | INTEGER DEFAULT 0 | |
| last_error | TEXT NULL | |
| created_at, updated_at | TIMESTAMPTZ | |

**UNIQUE:** `(company_id, event_fingerprint, is_current)` WHERE is_current=true

**UNIQUE (source):** `(source_system, source_type, source_id, event_type, is_current)` WHERE is_current=true

### 2.2. accounting_decision

| Поле | Тип |
|------|-----|
| id | UUID PK |
| event_id | UUID FK |
| decision_version | INTEGER |
| policy_version | VARCHAR(20) |
| included | BOOLEAN |
| reason | TEXT |
| manual_override | BOOLEAN |
| override_by | UUID |
| superseded_at | TIMESTAMPTZ NULL |

**UNIQUE:** `(event_id) WHERE superseded_at IS NULL`

### 2.3. decision_explanation (новая)

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID PK | |
| decision_id | UUID FK | |
| rule_code | VARCHAR(50) | `has_supporting_document`, `expense_allowed_for_usn` |
| weight | NUMERIC(5,4) | Вклад правила в решение |
| message | TEXT | Человекочитаемое описание |
| payload_json | JSONB | `{"matched": false, "missing": ["invoice"]}` |

### 2.4. recognition_snapshot (новая)

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID PK | |
| event_id | UUID FK | |
| snapshot_version | INTEGER | |
| inputs_json | JSONB | `{"documents":[...], "transactions":[...], "tax_regime": "USN_DR"}` |
| created_at | TIMESTAMPTZ | |

### 2.5. accounting_batch (v4)

| Поле | Тип |
|------|-----|
| id | UUID PK |
| company_id | UUID FK |
| source | VARCHAR(50) |
| external_batch_key | VARCHAR(128) NULL |
| checksum | VARCHAR(64) NULL |
| started_at | TIMESTAMPTZ |
| completed_at | TIMESTAMPTZ NULL |
| status | batch_status enum |

**UNIQUE:** `(external_batch_key)` WHERE external_batch_key IS NOT NULL

### 2.6. Остальные

tax_regime, tax_period, event_transaction, event_document — без изменений.

---

## 3. Статусная модель (processing × decision)

```
processing_state:        decision_state:
───────────────────      ────────────────
NEW                      (not applicable)
RECOGNIZING              (not applicable)
READY_FOR_DECISION       (not applicable)
DECIDING                 (not applicable)
DONE                     PENDING / INCLUDED / EXCLUDED / REVIEW_REQUIRED
FAILED                   (not applicable)
```

**Важно:** это независимые измерения. Комбинация:
- `DONE + INCLUDED` → готово, включено в учёт
- `DONE + EXCLUDED` → готово, исключено
- `DONE + REVIEW_REQUIRED` → готово, но нужен человек
- `FAILED + PENDING` → ошибка, ожидание retry
