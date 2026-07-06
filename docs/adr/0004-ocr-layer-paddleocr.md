|# ADR-0004|

Date: 2026-06-07|

## Context

Real Estate OS needs text extraction from Russian-language documents: scanned contracts, phone photos of passports/deeds, low-quality copies, and property reports. Three OCR engines were evaluated: Tesseract 5, EasyOCR, and PaddleOCR PP-OCRv4.

## Decision

**Primary engine: PaddleOCR PP-OCRv4** with PP-Structure layout analysis.

**Fallback engine: Tesseract 5** — used when PaddleOCR confidence < 0.6 on clean scans.

**LLM post-processing:** Qwen Local / DeepSeek Flash / DeepSeek Pro for field extraction and error correction, selected by document complexity.

## Reason

- **Russian text accuracy:** PP-OCR multilingual model (ml) outperforms EasyOCR and equals Tesseract LSTM on clean text, significantly better on noisy/photo text
- **Layout analysis:** PP-Structure is the only engine with built-in table, paragraph, and reading order detection — critical for contracts
- **Phone photo handling:** Built-in angle classification and distortion resistance handle real-world input without preprocessing
- **CPU efficiency:** Lightweight models (28 MB total) run at < 5s per page on CPU — EasyOCR needs ~2 GB memory
- **Fallback safety:** Tesseract covers edge cases (clean scans with unusual fonts) where PaddleOCR may have lower confidence

## Status

Accepted
