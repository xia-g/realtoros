# Product Roadmap — Post v3.0

**Baseline**: v3.0
**Date**: 2026-07-21
**Status**: Strategic direction

---

## Product Model

```
Product Layer
  Accounting · Real Estate · CRM · AI Copilot
    ↑
Knowledge Layer (v3.0 — 10 capabilities)
    ↑
Platform (frozen)
```

Epics drive product value. Capabilities remain internal building blocks.

---

## Epic 1 — Intelligent Document Intake

**Mission:**
Любой документ, загруженный в систему, автоматически превращается
в структурированные данные с измеримым качеством.

### Stream A — Intake

Гарантированно принять любой документ:
- PDF, JPG, PNG, TIFF, ZIP
- Drag-and-drop, multi-file, large documents
- Multi-page documents

### Stream B — OCR Quality

Не просто распознать, а измерить качество:
- OCR Confidence: 96% or 54%
- Needs manual review flag
- Quality threshold enforcement

### Stream C — Classification

Определить тип документа после OCR:
- Invoice, Bank Statement, Contract
- Acceptance Act, Power of Attorney
- Passport, Receipt
- Schema depends on document class

### Stream D — Entity Extraction

Извлечение данных по схеме, зависящей от класса:

**Invoice:** Supplier, Customer, VAT, Invoice Number,
Date, Amount, Currency, Payment Terms

**Bank Statement:** Transactions, Balance, Date Range

**Contract:** Parties, Dates, Terms, Amount

### Stream E — Validation

Проверка качества извлечения:
- VAT present? Date valid? Supplier exists?
- IBAN valid? Invoice duplicated? Totals correct?

### Stream F — Routing

Автоматическое направление документа после построения Knowledge:
- Invoice → Accounting
- Contract → Deal Lifecycle
- Lease → CRM
- Bank Statement → Reconciliation

### New Concept: Document Profile

```json
{
  "type": "Invoice",
  "confidence": 0.98,
  "language": "Dutch",
  "pages": 3,
  "ocr_quality": 0.97,
  "classification_confidence": 0.99,
  "extraction_confidence": 0.95,
  "needs_review": false
}
```

---

## Epic 2 — Accounting Engine

Строится на данных из Epic 1.
- Journal, Ledger, VAT
- Posting rules, Reconciliation
- Manual confirmation before posting

## Epic 3 — Reporting

- Trial Balance, P&L, Balance Sheet
- VAT Return, Tax registers
- Export for filing

## Epic 4 — AI Copilot

- Explain, Answer, Recommend
- Anomaly detection
- Natural language queries over Knowledge

---

## Planning Unit (new)

```
Epic → Streams → Features
                   ↑
              Capabilities (internal)
```

No more "capability for capability's sake."
Every Epic solves a real user problem.
