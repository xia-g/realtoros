# Document Intake Pipeline

## Overview

```
Upload → format detect → text extraction → classify → fields extract → events → obligations
```

## OCR & Text Extraction Setup

Tesseract 5.5.0 установлен локально (без sudo):

```
Binary:  /home/hermes/.local/bin/tesseract
Libs:    /home/hermes/.local/lib/
Data:    /home/hermes/.local/share/tessdata/ (rus + eng)
Env:     LD_LIBRARY_PATH=/home/hermes/.local/lib
         TESSDATA_PREFIX=/home/hermes/.local/share/tessdata
```

Python-пакеты (в venv `/home/xiag/real-estate-os/venv`):
- `pytesseract` — обёртка для tesseract
- `python-docx` — чтение DOC/DOCX
- `openpyxl` — чтение XLS/XLSX
- `pdfminer.six` — парсинг PDF
- `ocrmypdf` — OCR для сканов PDF (через pypdfium2)
- `Pillow` — обработка изображений

Системные утилиты:
- `/usr/bin/pdftotext` — извлечение текста из PDF
- `/usr/bin/pdftoppm` — конвертация PDF в изображения для OCR

## Supported Formats

| Format | Extension | Extractor | Notes |
|--------|-----------|-----------|-------|
| PDF (text) | .pdf | pdftotext | Быстро, digital PDF |
| PDF (scanned) | .pdf | pdftoppm → tesseract OCR | Медленно, зависит от качества скана |
| JPEG | .jpg, .jpeg | tesseract OCR | |
| PNG | .png | tesseract OCR | |
| DOCX | .docx | python-docx | |
| XLSX | .xlsx | openpyxl | Читает все листы |
| XML | .xml | ElementTree | |
| TXT | .txt | прямой | |
| ZIP | .zip | — | Хранится как контейнер |
| DOC | .doc | — | Старый формат, не поддерживается |

## Document Classification

Классификация по содержанию текста (не по имени файла).

### Categories

| Category | Keywords |
|----------|----------|
| `contract` | договор, контракт, соглашение, дкп, купли-продажи |
| `invoice` | счёт-фактура, счёт на оплату, инвойс, с/ф |
| `receipt` | кассовый чек, фискальный, чек, оплачено |
| `act` | акт выполненных работ, акт приема-передачи |
| `payment_order` | платёжное поручение, п/п, банк, списание |
| `municipal_contract` | торги, аукцион, муниципальное имущество, администрация, выкуп |
| `property_doc` | свидетельство, выписка, егрн, кадастровый, недвижимость |
| `other` | не распознан |

### Field Extraction

Из текста извлекаются регулярными выражениями:
- Суммы (рубли)
- Даты (ДД.ММ.ГГГГ)
- ИНН (10-12 цифр)
- Контрагент

## Auto-Creation Pipeline

При загрузке ДКП / муниципального контракта:

### Accounting Events
```
event_type: PURCHASE
amount: цена из документа
description: "Покупка недвижимости (документ: {classification})"
source_system: document_intake
```

### Recognition Snapshot
```
source: "document_intake"
document_id, classification, price
```

### Event-Document Link
```
event_document: event_id + document_id
```

### Obligations (on contract/municipal_contract with price)

| Type | Title | Amount | Due |
|------|-------|--------|-----|
| `vat_payable` | НДС как налоговый агент — покупка недвижимости | price × 20/120 | 25 число след. квартала |
| `tax_property` | Налог на имущество (коммерческая недвижимость) | 0 (оценка) | 1 декабря |

### Obligations (on invoice with price)

| Type | Title | Amount | Due |
|------|-------|--------|-----|
| `vat_payable` | НДС к уплате по счёту-фактуре | price × 20/120 | 25 число след. месяца |

## API Endpoints

### `POST /api/v1/upload/document`
Upload a document for processing.

**Request:** multipart/form-data
- `file` — the file (PDF, JPG, PNG, DOCX, XLSX, XML, TXT)
- `company_id` — UUID (optional, uses first active company)

**Response:**
```json
{
  "document_id": "uuid",
  "filename": "contract.pdf",
  "file_size": 123456,
  "classification": "contract",
  "confidence": 0.95,
  "events_created": 1,
  "obligations_created": 2,
  "extracted_text_preview": "ДОГОВОР КУПЛИ-ПРОДАЖИ...",
  "extracted_fields": {
    "amounts": [5000000.0],
    "dates": ["22.06.2026"],
    "inn": "780527855675",
    "counterparty": null
  },
  "warnings": [],
  "file_hash": "sha256..."
}
```

### `POST /api/v1/upload/bank`
Upload bank statement for import.

### `POST /api/v1/tax/optimize/property`
Analyze property purchase tax implications.

### `GET /api/v1/tax/optimize/tips?company_id=...`
Get generic optimization tips.

### `GET/POST/PATCH/DELETE /api/v1/obligations`
CRUD for obligations (payment calendar).

## Backend Files

| File | Purpose |
|------|---------|
| `backend/imports/documents/__init__.py` | Main intake pipeline |
| `backend/imports/ocr/__init__.py` | OCR classifier (legacy) |
| `backend/imports/bank/__init__.py` | Bank import parsers |
| `backend/api/routes/uploads.py` | Upload endpoints |
| `backend/api/routes/obligations.py` | Obligations CRUD |
| `backend/accounting/tax/optimizer.py` | Tax scenario engine |
| `backend/accounting/tax/optimize_routes.py` | Tax opt API |

## Frontend Pages

| URL | Description |
|-----|-------------|
| `/imports/documents` | Upload + OCR + classification result |
| `/imports` | Bank import |
| `/obligations` | Calendar of obligations |
| `/tax/optimization` | Tax scenario calculator |

## DB Tables

| Table | Schema | Purpose |
|-------|--------|---------|
| `documents` | public | Stored document metadata |
| `obligations` | public | Payment obligations calendar |
| `accounting.accounting_event` | accounting | Accounting events (created by pipeline) |
| `accounting.event_document` | accounting | Event-Document links |
| `accounting.recognition_snapshot` | accounting | AI recognition audit trail |

## Notes

- Tesseract запускается через subprocess (не через pytesseract) с кастомными LD_LIBRARY_PATH и TESSDATA_PREFIX
- При рестарте API (systemctl restart realtoros-api) obligations table создаётся автоматически через startup event
- Seed-данные обязательств не используются — всё создаётся через загрузку реальных документов
- Для scanned PDF: pdftoppm конвертит в PNG 300dpi, затем tesseract OCR
- Язык OCR: русский + английский (rus+eng)
