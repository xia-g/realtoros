"""
FactEvidence — evidence supporting a BusinessFact.

Immutable value object. Records why a fact exists.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.fact_source import FactSource


@dataclass(frozen=True)
class FactEvidence:
    """Доказательство факта: источник + уверенность + детали. Immutable."""
    source: FactSource
    confidence: FactConfidence
    detail: str = ""

    def __bool__(self) -> bool:
        return bool(self.source)

    @classmethod
    def from_source(cls, source: FactSource, confidence: FactConfidence | None = None) -> FactEvidence:
        return cls(
            source=source,
            confidence=confidence or FactConfidence.medium(),
        )
