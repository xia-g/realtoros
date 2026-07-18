"""
IdentityCandidate — fully built candidate before CanonicalEntity construction.

All identifiers, aliases, evidence are assembled here.
CanonicalEntity is constructed ONCE from this candidate.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.entity_types import EntityType
from domain.business_relationship.entity_alias import EntityAlias
from domain.business_relationship.normalized_identifier import NormalizedIdentifier
from domain.business_relationship.identity_evidence import IdentityEvidence


@dataclass(frozen=True)
class IdentityCandidate:
    """Кандидат для создания CanonicalEntity. Immutable. Полностью собран."""
    entity_type: EntityType
    display_name: str
    identifiers: tuple[NormalizedIdentifier, ...] = ()
    aliases: tuple[EntityAlias, ...] = ()
    evidence: tuple[IdentityEvidence, ...] = ()

    @property
    def primary_identifier(self) -> str:
        if self.identifiers:
            return self.identifiers[0].normalized
        return ""

    @property
    def identifier_count(self) -> int:
        return len(self.identifiers)
