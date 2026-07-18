"""
IdentityResolutionResult — output of identity resolution.
IdentityResolutionReport — audit report for a resolution session.

Both immutable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.identity_candidate import IdentityCandidate
from domain.business_relationship.identity_match_result import IdentityMatchResult


@dataclass(frozen=True)
class IdentityResolutionResult:
    """Результат разрешения идентичности для одного кандидата."""
    entity: CanonicalEntity | None = None
    candidate: IdentityCandidate | None = None
    match_result: IdentityMatchResult | None = None

    @property
    def is_new(self) -> bool:
        return self.entity is not None and self.match_result is not None and self.match_result.decision == "no_match"


@dataclass(frozen=True)
class IdentityResolutionReport:
    """Отчёт о сессии разрешения идентичности."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    results: tuple[IdentityResolutionResult, ...] = ()
    total_candidates: int = 0
    total_matched: int = 0
    total_created: int = 0
