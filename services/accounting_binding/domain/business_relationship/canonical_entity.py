"""
CanonicalEntity — canonical representation of a resolved identity.

Immutable aggregate. NO business logic.
NO matching. NO normalization. NO heuristics.
Pure data: one real-world object with its identifiers and aliases.

This is NOT the result of computations.
This is the canonical representation of already-resolved identity.
Identity resolution belongs in A3.2 (Identity Resolution Services).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.entity_types import EntityType
from domain.business_relationship.canonical_entity_id import CanonicalEntityId
from domain.business_relationship.entity_alias import EntityAlias
from domain.business_relationship.entity_identifier import EntityIdentifier
from domain.business_relationship.identity_evidence import IdentityEvidence
from domain.business_relationship.identity_metadata import IdentityMetadata


@dataclass(frozen=True)
class CanonicalEntity:
    """Каноническая бизнес-сущность.

    Immutable. Не содержит эвристик или алгоритмов.
    Не знает о Knowledge, Graph, Revision, Projection, Query.
    """
    entity_type: EntityType
    id: CanonicalEntityId
    display_name: str = ""
    identifiers: tuple[EntityIdentifier, ...] = ()
    aliases: tuple[EntityAlias, ...] = ()
    evidence: tuple[IdentityEvidence, ...] = ()
    metadata: IdentityMetadata = field(default_factory=IdentityMetadata)

    @property
    def primary_identifier(self) -> str:
        """Первый идентификатор (если есть)."""
        if self.identifiers:
            return self.identifiers[0].value
        return ""

    def __repr__(self) -> str:
        return (
            f"CanonicalEntity(type={self.entity_type.value}, "
            f"id={self.id}, "
            f"name={self.display_name or '- '}, "
            f"identifiers={len(self.identifiers)})"
        )
