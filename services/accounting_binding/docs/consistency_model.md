# Global Business State Consistency Model

Формальная модель истины для Accounting Binding v1.3.

---

## Source of Truth Hierarchy

Когда всё расходится — кто прав?

```
Level 1 (absolute truth)
  normalized_document
  └── immutable, frozen, не меняется
  └── источник: OCR или ручной ввод
  └── хранится: внешнее хранилище (S3, файлы)

Level 2 (derived truth)
  enriched_document
  └── replayable: deterministic из normalized_document
  └── conflict: пересчитать (replay from enrichment)

Level 3 (intent truth)
  accounting_document
  └── replayable: deterministic из enriched_document
  └── conflict: пересчитать (replay from mapping)
  └── но если APPROVED — проверять stale guard

Level 4 (money truth) — НЕЛЬЗЯ МЕНЯТЬ
  journal_entry
  └── append-only: REVERSE + NEW, не UPDATE
  └── conflict: journal_entry всегда прав
  └── если journal_entry ≠ accounting_document:
      → journal_entry это то, что реально попало в учёт
      → accounting_document нужно пересоздать
```

## Consistency Rules

### R1: journal_entry — absolute money truth

```
IF journal_entry EXISTS:
  → posted_amount is correct
  → accounting_document MAY be stale
  → корректировка: REVERSE + NEW journal_entry
  → НИКОГДА: UPDATE journal_entry
```

### R2: mapping_hash — idempotency + stale guard

```
IF mapping_hash MATCHES approved_mapping_hash:
  → approval valid, posting safe

IF mapping_hash ≠ approved_mapping_hash:
  → STALE_APPROVAL
  → recovery: REJECT → re-map → re-approve → post
```

### R3: posting_hash — dedup at storage level

```
IF posting_hash EXISTS in journal_entries:
  → DUPLICATE (idempotent)
  → return existing entry
  → НИКОГДА: insert duplicate

UNIQUE(posting_hash) — инвариант БД
```

### R4: process_state — orchestration guard

```
IF process_state == RUNNING:
  → posting in progress
  → НЕ запускать новый post
  → проверить: отвисший watchdog?

IF process_state == FAILED:
  → post не выполнился
  → retry (идемпотентно)
```

### R5: approval_revision — ordering guard

```
APPROVED:
  approval_revision = N
  approved_mapping_hash = H

STALE:
  mapping_hash ≠ H
  → approval недействителен
  → recovery: reject + re-map + re-approve
```

## State Matrix

| Domain State | Process State | Что означает | Действие |
|-------------|---------------|-------------|----------|
| DRAFT | PENDING | Не начат | — |
| READY | PENDING | Готов к review | Approval workflow |
| REVIEW | PENDING | На review | Ждёт решения |
| REVIEW | REPLAYING | Replay в процессе | Не мешать |
| APPROVED | PENDING | Утверждён, post не запущен | Outbox → worker → post |
| APPROVED | RUNNING | Posting в процессе | Ждать |
| APPROVED | FAILED | Posting упал | Retry |
| APPROVED | COMPLETED | Утверждён и разнесён | Норма |
| REJECTED | PENDING | Отклонён | Исправить → DRAFT |
| POSTED | COMPLETED | Разнесён | Только REVERSE |

## Conflict Resolution Matrix

| Конфликт | Source of Truth | Действие |
|----------|----------------|----------|
| normalized_doc vs enriched_doc | normalized | Replay enrichment |
| enriched_doc vs accounting_doc | enriched | Replay mapping |
| accounting_doc vs journal_entry | journal_entry | REVERSE + NEW |
| journal_entry vs report | journal_entry | Rebuild report |
| approval vs mapping_hash | mapping_hash | Stale guard |
| posting_hash vs journal_entry | posting_hash | Idempotent (DUPLICATE) |
| process_state vs реальность | watchdog | Timeout → FAILED → retry |

## Audit Requirements

Любое изменение состояния должно быть объяснимо:

```
WHAT changed: DRAFT → APPROVED
WHO changed: user_id / pipeline_auto
WHY changed: approval_policy.evaluate()
WHICH correlation: trace_id, pipeline_run_id
WHEN: timestamp
```

Эти 5W записываются в:
- ApprovalEvent (audit trail)
- Structured log (JSON)
- Outbox event (для async workers)
