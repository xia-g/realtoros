"""
ProvenanceSource, ProvenanceSourceType — source type for provenance.

Pure enum and immutable value object. No logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProvenanceSourceType(str, Enum):
    """Тип источника происхождения. Без логики."""
    DOCUMENT = "document"
    FACT = "fact"
    AGREEMENT = "agreement"
    ENTITY = "entity"
    KNOWLEDGE_EVENT = "knowledge_event"


@dataclass(frozen=True)
class ProvenanceSource:
    """Описание источника происхождения. Immutable."""
    source_type: ProvenanceSourceType
    source_id: str = ""
    description: str = ""