# Demo Dataset

## Contents

| File | Rows | Description |
|------|------|-------------|
| `bank_export.csv` | 1000 | Random bank transactions (2026) |
| `documents_manifest.json` | 300 | Document references with classifications |

## Generation

```bash
python datasets/demo/generate.py
```

## Schema

bank_export.csv:
- id, date, amount, currency, counterparty, description, account

documents_manifest.json:
- filename, classification (invoice/receipt/contract/act/payment_order/other)

## Usage

```python
from backend.imports.bank import import_file
result = await import_file("bank_export.csv", content, company_id, confirm=True)
```
