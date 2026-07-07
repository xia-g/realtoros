"""
EntityAlias — alternative representation of a canonical entity.

Immutable value object. No matching logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AliasType(str, Enum):
    NAME_VARIANT = "name_variant"
    ABBREVIATION = "abbreviation"
    TRANSLITERATION = "transliteration"
    TYPO = "typo"
    HISTORICAL = "historical"


@dataclass(frozen=True)
class EntityAlias:
    """Альтернативное представление сущности. Immutable."""
    original_value: str
    normalized_value: str
    alias_type: AliasType = AliasType.NAME_VARIANT
    confidence: float = 0.8
    source_document_id: str = ""
