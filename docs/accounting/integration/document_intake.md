# Document Intake — Integration Guide

## Pipeline

```
Upload → document store → OCR (mock) → classify → event linking → recognition_snapshot
```

## Supported Formats

| Format | Extension | Status |
|--------|-----------|--------|
| PDF | .pdf | ✅ |
| JPEG | .jpg, .jpeg | ✅ |
| PNG | .png | ✅ |
| ZIP | .zip | ✅ |

## Integration

```python
from backend.imports.documents import DocumentIntake

result = await DocumentIntake.process(
    filename="invoice_001.pdf",
    content=file_bytes,
    company_id=company_id,
)
print(f"Doc: {result.document_id}, Class: {result.classification}, Conf: {result.confidence}")
```

## Classification Categories

| Category | Trigger Keywords |
|----------|-----------------|
| invoice | счет-фактура, invoice, счет на оплату |
| receipt | чек, receipt, кассовый чек |
| contract | договор, contract, соглашение |
| act | акт, act, акт выполненных работ |
| payment_order | платеж, payment, платежное поручение |
| other | default |

## Recognition Snapshot

A `recognition_snapshot` is created with:
- `document_id`
- `classification` (document type)
- `source: "document_intake"`
