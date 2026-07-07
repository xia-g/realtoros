"""
AgreementResolutionResult + AgreementResolutionReport — output of the resolver.

Immutable. Deterministic. Side-effect free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_candidate import AgreementCandidate
from domain.business_relationship.agreement_match_result import AgreementMatchResult
from domain.business_relationship.agreement_participant import AgreementParticipant


@dataclass(frozen=True)
class AgreementResolutionResult:
    """Итоговый результат разрешения соглашения."""
    agreement: Agreement | None = None
    participants: tuple[AgreementParticipant, ...] = ()
    match_result: AgreementMatchResult | None = None
    candidate: AgreementCandidate | None = None
    evidence: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        ag = self.agreement
        if not ag:
            return "AgreementResolutionResult(empty)"
        roles = ", ".join(f"{p.participant_role.value}" for p in self.participants[:3])
        return (
            f"AgreementResolutionResult("
            f"{ag.summary}, roles=[{roles}], "
            f"match={self.match_result.decision.value if self.match_result else 'none'})"
        )


@dataclass(frozen=True)
class AgreementResolutionReport:
    """Отчёт о сессии разрешения. Для аудита и explainability."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    candidates: tuple[AgreementCandidate, ...] = ()
    match_results: tuple[AgreementMatchResult, ...] = ()
    resolutions: tuple[AgreementResolutionResult, ...] = ()
    total_facts_processed: int = 0
    total_entities_processed: int = 0
