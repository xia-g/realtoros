# OCR Layer Architecture

## Overview

OCR layer for Real Estate OS — extracts text from scanned documents, phone photos, and low-quality images. Designed for Russian-language real estate documents: contracts, passports, extracts, deeds, receipts, reports.

## Document Types Requiring OCR

| Type | Content | Quality | Complexity |
|------|---------|---------|------------|
| contract | Russian legal text, mixed fonts | scans (clean/low) | high (multi-page, tables) |
| passport | Structured fields, Cyrillic | photos (variable) | medium (fixed layout) |
| extract | Tabular data, addresses | scans (clean) | medium (tables) |
| deed | Form text, signatures | scans (low) | medium |
| receipt | Printed/mobile text | photos (low) | low |
| statement | Tabular financial data | scans (clean) | medium (tables) |
| report | Mixed text, images | scans/photos | high (complex layout) |
| photo | Property images with text | photos (variable) | low |

## OCR Engine Selection

### Comparison

| Criterion | Tesseract 5 | EasyOCR | PaddleOCR (PP-OCRv4) |
|-----------|-------------|---------|---------------------|
| **Russian text** | Good (LSTM + rus.traineddata) | Good | Excellent |
| **Scanned contracts** | Excellent (clean >300 DPI) | Good | Excellent |
| **Phone photos** | Poor (needs heavy preprocessing) | Good | Excellent |
| **Low quality scans** | Poor (requires deskew/denoise) | Fair | Good (built-in enhancement) |
| **Layout analysis** | External (tesseract.js, hOCR) | None | Built-in (PP-Structure) |
| **Table recognition** | External (tesseract table) | None | Built-in |
| **Text orientation** | Limited (osd mode) | Built-in | Built-in (angle classifier) |
| **CPU performance** | Fast | Slow | Moderate (optimized) |
| **GPU support** | Yes (via tessercpp) | Yes (PyTorch) | Yes (PaddlePaddle) |
| **Training capability** | Custom font training | No | Fine-tuning supported |
| **Memory usage** | ~200 MB | ~2 GB | ~500 MB |
| **Python API quality** | pypi (subprocess) | Excellent (torch) | Good |
| **Documentation** | Excellent | Good | Fair (Chinese-heavy) |
| **Maintenance** | Active (community) | Active | Very active (Baidu) |
| **License** | Apache 2.0 | Apache 2.0 | Apache 2.0 |

### Decision: PaddleOCR

**Primary engine: PaddleOCR PP-OCRv4** with PP-Structure layout analysis.

Rationale:
1. **Russian text accuracy** — PP-OCR multilingual model (ml) includes robust Cyrillic support with character-level recognition
2. **Mixed quality handling** — PP-OCR system is specifically trained on real-world data (blur, low light, perspective distortion)
3. **Layout analysis** — PP-Structure detects paragraphs, tables, headers, reading order — critical for contract parsing
4. **Table recognition** — Built-in table structure recognition for passports, extracts, bank statements
5. **CPU efficiency** — Optimized lightweight models (det ~14 MB, rec ~12 MB, cls ~2 MB) run on CPU at reasonable speed
6. **Phone photo handling** — Text angle classifier (0°/90°/180°/270°) and distortion resistance built in

**Fallback: Tesseract 5** — Will be used as secondary engine when PaddleOCR fails to meet confidence threshold (< 0.6) on clean scans where Tesseract excels.

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    OCR Pipeline                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  PDF Upload                                               │
│     │                                                     │
│     ▼                                                     │
│  PDF→Image Converter  (pdf2image + poppler)               │
│     │                                                     │
│     ▼                                                     │
│  ├─────────────────────────────────────────────────────┤  │
│  │  Preprocessor                                        │  │
│  │  ├─ Orientation correction                           │  │
│  │  ├─ Deskew (≤ 15° auto)                              │  │
│  │  ├─ Denoise (bilateral filter)                       │  │
│  │  └─ Contrast enhancement (CLAHE)                     │  │
│  ├─────────────────────────────────────────────────────┤  │
│     │                                                     │
│     ▼                                                     │
│  ├─────────────────────────────────────────────────────┤  │
│  │  PaddleOCR (PP-OCRv4)                                │  │
│  │  ├─ Text Detection (DBNet) → bounding boxes           │  │
│  │  ├─ Angle Classification → corrected crops            │  │
│  │  └─ Text Recognition (SVTR) → Unicode strings         │  │
│  ├─────────────────────────────────────────────────────┤  │
│     │                                                     │
│     ▼                                                     │
│  ├─────────────────────────────────────────────────────┤  │
│  │  Layout Analyzer (PP-Structure)                      │  │
│  │  ├─ Table detection + cell extraction                 │  │
│  │  ├─ Paragraph grouping + reading order                │  │
│  │  └─ Header/footer separation                          │  │
│  ├─────────────────────────────────────────────────────┤  │
│     │                                                     │
│     ▼                                                     │
│  ├─────────────────────────────────────────────────────┤  │
│  │  Post-processor                                      │  │
│  │  ├─ Confidence threshold filter (< 0.6 → fallback)    │  │
│  │  ├─ Tesseract fallback (if Paddle confidence low)     │  │
│  │  └─ LLM enhancement (field extraction, correction)    │  │
│  ├─────────────────────────────────────────────────────┤  │
│     │                                                     │
│     ▼                                                     │
│  Result: OCRResult(text, confidence, layout, bbox[])      │
│     │                                                     │
│     ▼                                                     │
│  Storage                                                  │
│  ├─ ocr_results table (extracted text + metadata)         │
│  ├─ documents.file_hash ↔ ocr_results.document_hash       │
│  └─ AI Service for field extraction                       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Preprocessor

Converts raw input into format PaddleOCR handles best.

```python
class OCRPreprocessor:
    def process(image: np.ndarray) -> np.ndarray:
        # 1. Orientation: EXIF metadata + angle classifier
        # 2. Deskew: Hough line transform (max 15°)
        # 3. Denoise: Bilateral filter (preserves edges)
        # 4. Enhance: CLAHE (contrast limited adaptive histogram equalization)
        return enhanced_image
```

**PDF handling:** Convert to images at 300 DPI using `pdf2image` (poppler wrapper). Multi-page PDFs produce one image per page.

### 2. PaddleOCR Engine (Primary)

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_angle_cls=True,          # auto-rotate text
    lang='ml',                   # multilingual (includes Russian)
    use_gpu=False,               # CPU inference
    enable_mkldnn=True,          # Intel acceleration
    det_db_thresh=0.3,           # detection threshold (lower → more text found)
    rec_batch_num=6,             # batch size for recognition
)
```

**Model composition (PP-OCRv4):**
- **Detection** (DBNet) — `en_PP-OCRv4_det` — text region detection
- **Classification** — `ch_ppocr_mobile_v2.0_cls` — text orientation (0/90/180/270°)
- **Recognition** (SVTR) — `en_PP-OCRv4_rec` — text string recognition
- **Table recognition** — `en_ppstructure_mobile_v2.0_SLANet` — table structure detection

**Language:** Use `lang='ml'` (multilingual) which includes Russian + English + common latin characters. This handles mixed-language real estate contracts.

### 3. Layout Analyzer

Contracts and documents need structural understanding beyond raw text.

```python
from paddleocr import PPStructure

engine = PPStructure(
    table=True,       # table detection
    ocr=True,         # text extraction inside cells
    lang='ml',
)

result = engine(image)
# Output: list of dicts with type='table'|'text', content, cell_texts
```

**Layout types detected:**
- **Text block** — paragraph, header, footer
- **Table** — structured rows/columns with cell text
- **Figure** — image with caption (mark for LLM analysis)

### 4. Tesseract Fallback

Used when PaddleOCR confidence < 0.6 on clean scans.

```python
import pytesseract

def tesseract_fallback(image: np.ndarray, lang='rus+eng') -> OCRResult:
    data = pytesseract.image_to_data(
        image,
        lang=lang,
        config='--oem 3 --psm 6',  # LSTM + assume uniform block
        output_type=pytesseract.Output.DICT,
    )
    return OCRResult.from_tesseract(data)
```

**Trigger rules:**
- Full page confidence < 0.6 → fallback entire page
- Individual block confidence < 0.4 → fallback that block only
- Table recognition failure → fallback to raw text extraction

### 5. LLM Post-Processing

LLM corrects OCR errors and extracts structured fields.

```python
class OCRPostProcessor:
    def extract_fields(raw_text: str, doc_type: str) -> dict:
        # Uses Qwen Local (simple extraction) or DeepSeek Flash (medium)
        # Prompt:
        prompt = f"""
        Извлеки структурированные данные из OCR-текста документа.
        Тип документа: {doc_type}
        
        Требования:
        - Исправь очевидные OCR-ошибки (цифры, буквы)
        - Извлеки: даты, суммы, имена, адреса, номера документов
        - Верни в формате JSON
        
        Текст:
        {raw_text}
        """
        return llm.extract(prompt, model=model_for_complexity(doc_type))
```

**Model selection (from development rules):**
- Simple extraction (passport, receipt): Qwen Local
- Medium (extract, deed, statement): DeepSeek Flash
- Complex (contract, report): DeepSeek Pro

### 6. Result Storage

```sql
CREATE TABLE ocr_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    layout JSONB,              -- bounding boxes, reading order, table structure
    extracted_fields JSONB,     -- LLM-extracted structured data
    ocr_engine VARCHAR(20) NOT NULL,  -- 'paddleocr' | 'tesseract'
    page_count INTEGER NOT NULL DEFAULT 1,
    processing_time_ms INTEGER,
    model_version VARCHAR(50),  -- PP-OCRv4.0, Tesseract 5.4
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ocr_results_document ON ocr_results(document_id);
CREATE INDEX idx_ocr_results_confidence ON ocr_results(confidence);
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Single page latency (CPU) | < 5 sec | PaddleOCR pipeline |
| Single page latency (GPU) | < 1 sec | With CUDA |
| Batch throughput (CPU) | 12 pages/min | 6 parallel workers |
| Russian text accuracy (clean) | > 95% | 300 DPI scans |
| Russian text accuracy (photo) | > 85% | Phone camera |
| Russian text accuracy (low quality) | > 75% | Blurry/noisy |
| Table extraction accuracy | > 90% | Structured tables |

## Error Handling Strategy

| Failure Mode | Handler |
|--------------|---------|
| PaddleOCR confidence < 0.6 | Tesseract fallback |
| Both engines fail | Flag for manual review |
| PDF read error | Return error, log file path |
| OOM (large image) | Downscale to 2000px longest side |
| Network unavailable | Use local models only |
| LLM extraction timeout | Return raw OCR text |

## Data Model Integration

The OCR layer integrates with the existing `documents` table:

```
documents (existing)
  ├── id UUID
  ├── file_path VARCHAR  → image/PDF path
  ├── mime_type VARCHAR  → 'application/pdf', 'image/jpeg', etc.
  ├── file_hash VARCHAR  → SHA-256 (dedup)
  └── status VARCHAR    → 'pending' → 'processing' → 'completed' | 'failed'
        ↓
ocr_results (new)
  ├── document_id UUID   → FK to documents.id
  ├── raw_text TEXT      → full extracted text
  ├── confidence FLOAT   → average confidence
  ├── layout JSONB       → structure metadata
  └── extracted_fields JSONB → LLM output
        ↓
AI Service
  ├── Lead scoring from passport data
  ├── Contract clause extraction
  └── Property description from photo text
```

## Implementation Priority

1. **Phase 1** — Core pipeline
   - PaddleOCR installation + basic text extraction
   - PDF→Image conversion
   - Russian language testing
   - Result storage

2. **Phase 2** — Enhancement
   - PP-Structure layout analysis
   - Table recognition
   - Tesseract fallback
   - Preprocessing pipeline

3. **Phase 3** — Intelligence
   - LLM post-processing
   - Field extraction by document type
   - Multi-page document handling
   - Batch processing queue

## Installation

```bash
# Core dependencies
pip install paddlepaddle paddleocr  # PaddleOCR
pip install pdf2image poppler-utils  # PDF handling
pip install pytesseract tesseract    # Fallback
pip install opencv-python-headless   # Preprocessing

# Or via requirements
pip install -r backend/requirements-ocr.txt

# System dependencies
sudo apt install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng poppler-utils
```

## Related Documentation

- `docs/domain/domain_model.md` — Document entity definition
- `docs/domain/database_schema_v1.md` — ocr_results table design
- `docs/development_rules.md` — AI model selection guidelines
- `docs/roadmap/mvp.md` — Document Import is MVP item #2
