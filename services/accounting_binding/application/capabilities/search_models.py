"""
Knowledge Search v1 — domain contract: query and result models.

Pure dataclasses. No Platform imports. No business logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class KnowledgeSearchQuery:
    """Deterministic search query over KnowledgeRevision.

    All filters are AND-combined. No ranking or fuzzy matching.
    """
    source_document_id: str | None = None
    reason_contains: str | None = None          # ILIKE substring match
    created_by: str | None = None               # exact match
    created_after: datetime | None = None        # inclusive
    created_before: datetime | None = None       # inclusive
    revision_number_min: int | None = None
    revision_number_max: int | None = None

    # Pagination
    cursor: str | None = None                   # base64(created_at||revision_id)
    limit: int = 20                              # 1..100

    # Sorting — only these two fields supported in v1
    sort_field: str = "created_at"               # "created_at" | "revision_number"
    sort_direction: str = "DESC"                 # "ASC" | "DESC"


@dataclass(frozen=True)
class SearchResultItem:
    """Single search result — a matched KnowledgeRevision."""
    revision_id: str
    revision_number: int
    source_document_id: str
    created_at: str
    reason: str
    created_by: str


@dataclass(frozen=True)
class KnowledgeSearchResult:
    """Deterministic result of a KnowledgeSearchQuery.

    Invariants:
      - Same query → same result (ordering + cursor)
      - Empty result → [] + cursor: null
      - Last page → cursor: null
    """
    items: tuple[SearchResultItem, ...] = ()
    next_cursor: str | None = None
    total_matches: int = 0


# ─── Helpers for cursor pagination ───────────────────────────────

import base64


def encode_search_cursor(created_at: str, revision_id: str) -> str:
    raw = f"{created_at}||{revision_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_search_cursor(cursor: str) -> tuple[str, str]:
    padded = cursor + "=" * (4 - len(cursor) % 4) if len(cursor) % 4 else cursor
    raw = base64.urlsafe_b64decode(padded.encode()).decode()
    parts = raw.split("||", 1)
    if len(parts) != 2:
        raise ValueError("Invalid cursor format")
    return parts[0], parts[1]
