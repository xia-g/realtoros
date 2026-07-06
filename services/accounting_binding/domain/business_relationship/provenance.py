"""
Provenance — immutable value object.

Tracks WHERE a fact was extracted from.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentRevision:
    """Конкретная ревизия документа."""
    document_id: str
    revision: int = 1
    created_by: str = "ocr_v1.1"  # ocr_v1.1 | user_fix | semantic_v1.5


@dataclass(frozen=True)
class Provenance:
    """Откуда был извлечён факт."""
    document_revision: DocumentRevision
    page: int = 0
    ocr_fragment: str = ""              # цитата из raw_text
    extractor_version: int = 1
    extraction_method: str = "regex"    # regex | heuristic | semantic
