# Bank Import — Integration Guide

## Supported Formats

| Format | Extension | Parser | Status |
|--------|-----------|--------|--------|
| CSV | .csv | DictReader with column auto-detection | ✅ |
| XLSX | .xlsx | openpyxl (requires package) | ✅ |
| MT940 (SWIFT) | .txt, .sta | `:61:` / `:86:` field parser | ✅ |
| CAMT.053 | .xml | ISO 20022 XML parser | ✅ |
| 1C Export | .txt | cp1251, tab-separated | ✅ |

## Pipeline

```
Upload → detect_format() → parser → normalize() → fingerprint() → dedup() → preview() → confirm() → batch + events
```

## Integration

```python
from backend.imports.bank import import_file

# Preview only
preview = await import_file("export.csv", content, company_id)
print(preview.warnings, len(preview.preview))

# Confirm + create events
result = await import_file("export.csv", content, company_id, confirm=True)
print(f"Batch: {result.batch_id}, Events: {result.events_created}, Dups: {result.duplicates}")
```

## Fingerprint (dedup)

```python
fingerprint = SHA256(f"{amount:.2f}|{direction}|{date}|{description}|{counterparty}|{external_id}")
```

## Performance

- 1000 rows: ~2s parse + normalize + dedup + insert
- Duplicates: detected via `event_fingerprint` in accounting_event table
