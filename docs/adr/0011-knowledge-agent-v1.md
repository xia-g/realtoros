|# ADR-0011|

Date: 2026-06-07|

## Context

Five separate architecture subsystems exist (OCR, Classifier, Extraction, Resolution, Knowledge Graph) but there is no orchestrator that ties them together into an end-to-end document processing pipeline. Each subsystem is documented independently, with no shared pipeline state, error handling, or retry logic.

## Decision

Create a **Knowledge Agent V1** — a centralized orchestrator that:

1. **Owns the full pipeline:** Ingestion → OCR → Classification → Extraction → Resolution → Storage → Graph. Each stage is async, independently retryable, and persists state in `documents.status`.

2. **Routes AI by task:** 
   - PaddleOCR for text extraction
   - TF-IDF + SVM for fast classification
   - Qwen Local for simple documents (passport, receipt)  
   - DeepSeek Flash for medium complexity
   - DeepSeek Pro for complex contracts
   - ChatGPT as last-resort fallback for human review edge cases

3. **Calculates overall document confidence** as `min(ocr, classification, extraction)` — the weakest link determines review need.

4. **Enables human-in-the-loop review** via Telegram inline keyboard when confidence < 0.85 or validation errors occur.

5. **Exposes 8 MCP tools** for document processing, entity search, graph queries, and review workflow.

## Reason

- **Single orchestrator** eliminates coordination gaps between independently-designed subsystems
- **Pipeline state in DB** (`documents.status`) enables crash recovery and retry from any stage
- **Confidence as minimum** is more conservative than average — prevents false positives
- **SHA-256 dedup** prevents duplicate processing
- **MCP tools** make the agent accessible from Telegram, CLI, or API with the same interface

## Status

Accepted
