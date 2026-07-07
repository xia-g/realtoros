"""
CanonicalProperty — canonical property representation.

Immutable. NO business logic. Placeholder for phase A3.x.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.entity_alias import EntityAlias


@dataclass(frozen=True)
class CanonicalProperty:
    """Канонический объект недвижимости. Immutable."""
    id: str = ""
    cadastral_number: str = ""
    normalized_address: str = ""
    area: float = 0.0
    floor: int = 0
    object_type: str = ""
    aliases: tuple[EntityAlias, ...] = ()

    @property
    def confidence(self) -> float:
        return 0.0  # placeholder

    def confirm(self, document_id: str, agreement_id: str = ""):
        """Placeholder for A3.2. Does nothing on immutable stub."""
