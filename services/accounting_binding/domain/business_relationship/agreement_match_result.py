"""
AgreementMatchResult — outcome of matching a candidate against existing agreements.

Immutable. Produced by AgreementMatcher. Decision only, no mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_candidate import AgreementCandidate


class MatchDecision(str, Enum):
    MATCHED = "matched"                     # exact match found
    NO_MATCH = "no_match"                   # new agreement needed
    AMBIGUOUS = "ambiguous"                 # multiple candidates match
    CONFLICT = "conflict"                   # contradictory information


@dataclass(frozen=True)
class AgreementMatchResult:
    """Результат сопоставления кандидата с существующими соглашениями."""
    decision: MatchDecision
    candidate: AgreementCandidate
    matched_agreement: Agreement | None = None
    reason: str = ""
    confidence: float = 1.0
