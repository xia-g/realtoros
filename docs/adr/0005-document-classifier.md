|# ADR-0005|

Date: 2026-06-07|

## Context

Documents uploaded to Real Estate OS need automatic classification into 7 expected types (sale contract, agency contract, rental contract, passport, EGRN extract, receipt, power of attorney) before field extraction and AI processing.

## Decision

Adopt a 3-stage cascading classifier:

1. **Stage 1: Rule-based** — file extension, MIME type, page count, keyword matching, layout signature. Coverage: 30–40%. Cost: zero.
2. **Stage 2: ML-based (TF-IDF + SVM)** — character n-gram vectorization (handles OCR typos), linear SVM with calibrated probabilities. Coverage: 40–50%. Cost: ~50 ms.
3. **Stage 3: LLM-based (DeepSeek Flash)** — full OCR context with structured JSON output (Pydantic schema). Coverage: 15–20%. Cost: ~2–5 sec.

**Storage:** New `document_classifications` table with category (broad type), subtype (fine-grained), confidence, method, and manual review support.

**Mapping:** Subtypes map to existing `documents.document_type` via a category+subtype ENUM system.

## Reason

- **Cost efficiency:** Stage 1 + 2 handle > 75% of documents without LLM calls — critical for batch processing of large uploads
- **Accuracy:** 3-stage cascade provides 95%+ overall accuracy while keeping LLM usage minimal
- **Robustness:** Fallback cascade (rule → ML → LLM → manual) handles all failure modes
- **Type-system compatibility:** Subtypes extend the existing `document_type` enum without schema migration
- **Trainable:** ML model improves over time with weekly retraining on human-verified samples

## Status

Accepted
