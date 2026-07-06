# OCR Classification — Integration Guide

## Architecture

```
OCR text → Classifier.classify() → ClassificationResult(doc_type, confidence, evidence)
                                      ↓
                              Manual override (optional)
                                      ↓
                              Reclassification
```

## Categories

- `invoice` — счет-фактура, invoice
- `receipt` — чек, receipt
- `contract` — договор, contract
- `act` — акт, act
- `payment_order` — платежное поручение
- `other` — default

## Integration

```python
from backend.imports.ocr import Classifier

# Automatic
result = Classifier.classify(ocr_text="счет-фактура №123 от 01.02.2026", filename="invoice_123.pdf")
print(result.doc_type, result.confidence, result.evidence)

# Manual override
result = await Classifier.reclassify(doc_id="...", new_type="invoice", reason="Accountant verified")
```

## Confidence

| Case | Confidence |
|------|-----------|
| Keywords matched | 0.9 |
| No keywords ("other") | 0.5 |
| Manual override | 1.0 |

## Versioning

`classifier_version = "1.0.0"` — incremented on model updates.
All classifications are traceable to a specific classifier version.
