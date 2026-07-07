"""
AuthorityEvaluator — determines authority level from knowledge events.

Deterministic. Domain rules only. NO ML. NO probabilities.
"""
from __future__ import annotations

from domain.business_relationship.ke_enums import AuthorityLevel
from domain.business_relationship.ke_event import KnowledgeEvent


class AuthorityEvaluator:
    """Оценивает уровень авторитетности на основе события.

    Rules (deterministic, no probabilities):
      - Entity with OFFICIAL-level source → OFFICIAL
      - Merged/superseded events → STRONG
      - Agreement-linked events → NORMAL
      - Simple created/updated → WEAK
      - Unknown → UNKNOWN
    """

    @staticmethod
    def evaluate(event: KnowledgeEvent) -> AuthorityLevel:
        """Evaluate authority level from a knowledge event."""
        if event.authority_level == "official":
            return AuthorityLevel.OFFICIAL
        if event.event_type in ("merged", "superseded"):
            return AuthorityLevel.STRONG
        if bool(event.agreement_id):
            return AuthorityLevel.NORMAL
        if event.event_type in ("created", "updated", "terminated"):
            return AuthorityLevel.WEAK
        return AuthorityLevel.UNKNOWN
