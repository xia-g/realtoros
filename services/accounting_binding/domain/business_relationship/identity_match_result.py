"""
IdentityMatchResult + MatchDecision — outcome of matching a candidate.

Immutable. Decision only. No side effects. No mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.identity_candidate import IdentityCandidate


class MatchDecision(str, Enum):
    MATCH = "match"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class IdentityMatchResult:
    """Результат сопоставления кандидата с существующими сущностями."""
    decision: MatchDecision
    candidate: IdentityCandidate
    matched_entity: CanonicalEntity | None = None
    reason: str = ""
