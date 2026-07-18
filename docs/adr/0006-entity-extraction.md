|# ADR-0006|

Date: 2026-06-07|

## Context

After OCR text extraction and document classification, the system needs to extract structured entities (Client, Property, Address, Price, Deal, Date, Organization) from Russian-language real estate documents for database insertion.

## Decision

Adopt a 2-stage extraction pipeline with cross-entity validation:

1. **Stage 1: Pattern-based extraction** — regex rules for structured fields (passport numbers, phones, INN, prices, dates). Coverage: 30–40%. Zero cost.
2. **Stage 2: LLM-based extraction** — document-type-specific prompts returning typed JSON (Pydantic schemas). Model selected by document complexity (Qwen Local for simple, DeepSeek Flash for medium, DeepSeek Pro for complex contracts).

**Output:** 7 JSON schemas (Client, Property, Address, Price, Deal, Date, Organization) with per-field confidence scoring.

**Validation:** Per-field rules (patterns, bounds), cross-entity consistency (price match, date chronology, party matching), required fields per document type.

**Storage:** New `extracted_entities` table with full JSONB result, confidence scores, validation report, and status workflow (auto_accept → human_review → rejected).

## Reason

- **Pattern boost:** Regex catches high-confidence structured fields (phones, INN, dates) before LLM — reduces hallucination risk
- **Hybrid confidence:** Pattern + LLM agreement boosts confidence by 0.10; conflict penalizes by 0.15
- **Document-type awareness:** Different prompt templates per document type ensure relevant fields are extracted
- **Validation safety:** Cross-entity rules prevent logically impossible data (date before contract, commission > price)
- **Confidence escalation:** 3-tier threshold system (auto ≥ 0.85, review ≥ 0.60, reject < 0.40) balances automation with quality

## Status

Accepted
