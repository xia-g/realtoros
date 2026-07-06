"""
Accounting Binding — Архитектурное описание.

Ветка: services/accounting_binding/
Статус: DESIGN PHASE
Дата: 2026-06-25

## Pipeline

normalized_document (OCR, immutable)
    ↓ enrichment: canonical entities, counterparty, dedup
enriched_document
    ↓ validation: schema, rules, confidence
validated (EnrichedDocument)
    ↓ mapping: account resolution, tax, dimensions
accounting_document
    ↓ approval: DRAFT → READY → REVIEW → APPROVED → REJECTED → POSTED
approved (AccountingDocument)
    ↓ posting: double-entry ledger
journal_entry
    ↓ reporting: trial_balance, ledger_view, export

## Architecture

- DDD + Hexagonal Architecture
- Каждый этап — независимый доменный сервис
- Контракты (Pydantic frozen) — единственная точка обмена
- Idempotent: одинаковый normalized_document → одинаковый journal_entry
- Exceptions НЕ используются как бизнес-логика

## Контракты

| Контракт | Этап создания | Статус |
|----------|---------------|--------|
| NormalizedDocument | OCR (вход) | FROZEN, READ-ONLY |
| EnrichedDocument | Enrichment | DESIGNED |
| AccountingDocument | Mapping | DESIGNED |
| JournalEntry | Posting | DESIGNED |

## Домены

| Домен | Вход | Выход | Отвечает за |
|-------|------|-------|-------------|
| Enrichment | NormalizedDocument | EnrichedDocument | canonical entities, counterparty, dedup |
| Validation | EnrichedDocument / AccountingDocument | ValidationResult | schema, rules, confidence |
| Mapping | EnrichedDocument | AccountingDocument | account resolution, tax, dimensions |
| Approval | AccountingDocument | AccountingDocument(status) | workflow states |
| Posting | AccountingDocument | JournalEntry | double-entry, idempotency |
| Reporting | JournalEntry[] | TrialBalance / LedgerView | projections, no business logic |

## Архитектурные правила

- ✅ DDD, Hexagonal Architecture
- ✅ Typed contracts (Pydantic frozen)
- ✅ Idempotent workflows
- ✅ Explicit state transitions
- ❌ shared mutable state
- ❌ implicit coupling
- ❌ обратные зависимости на OCR
- ❌ бухгалтерская логика в ingestion
