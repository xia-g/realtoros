"""
FactSource — source of a BusinessFact.

Immutable value object. Describes which document and revision
produced this fact. Complements Provenance with source metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FactSource:
    """Источник факта: документ + ревизия + метод извлечения. Immutable."""
    document_id: str
    revision: int = 1
    method: Literal["ocr", "regex", "semantic", "manual"] = "ocr"

    def __bool__(self) -> bool:
        return bool(self.document_id)

    @classmethod
    def ocr(cls, document_id: str, revision: int = 1) -> FactSource:
        return cls(document_id=document_id, revision=revision, method="ocr")

    @classmethod
    def semantic(cls, document_id: str, revision: int = 1) -> FactSource:
        return cls(document_id=document_id, revision=revision, method="semantic")

    @classmethod
    def manual(cls, document_id: str) -> FactSource:
        return cls(document_id=document_id, method="manual")
