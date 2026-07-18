"""
AgreementReference — typed reference between Agreement and other entities.

Immutable value object.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReferenceKind(str, Enum):
    DOCUMENT = "document"
    AGREEMENT = "agreement"
    ENTITY = "entity"
    PROPERTY = "property"
    DEAL = "deal"


@dataclass(frozen=True)
class AgreementReference:
    """Ссылка на связанную сущность. Immutable."""
    kind: ReferenceKind
    target_id: str
    role: str = ""  # "supporting_doc", "amends", "supersedes"
