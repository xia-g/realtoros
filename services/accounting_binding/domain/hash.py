"""
Canonical hashing для идемпотентности.

Правило:
- canonical JSON
- sort_keys
- exclude_none
- utf8
- sha256

Никогда не включать: created_at, updated_at, id, trace_timestamp.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


EXCLUDE_KEYS = frozenset({
    "id", "entry_id", "document_id", "accounting_document_id",
    "company_id", "trace_id", "created_at", "updated_at",
    "posted_at", "completed_at", "generated_at",
    "schema_version", "mapping_hash", "posting_hash",
    "source_document",
})


def canonical_hash(data: dict[str, Any]) -> str:
    """Вычислить canonical SHA256 хеш от словаря."""
    clean = _clean(data)
    raw = json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _clean(value: Any) -> Any:
    """Рекурсивно очистить от exclude-ключей и None."""
    if isinstance(value, dict):
        return {
            k: _clean(v)
            for k, v in value.items()
            if v is not None and k not in EXCLUDE_KEYS
        }
    elif isinstance(value, list):
        return [_clean(item) for item in value if item is not None]
    elif isinstance(value, (int, float, str, bool)):
        return value
    else:
        # Для Decimal, datetime и тд
        return str(value)
