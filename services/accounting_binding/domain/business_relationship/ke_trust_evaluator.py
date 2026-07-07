"""
TrustEvaluator — determines trust level from knowledge events.

Deterministic. Domain rules only. NO ML. NO heuristics.
"""
from __future__ import annotations

from domain.business_relationship.ke_enums import TrustLevel
from domain.business_relationship.ke_event import KnowledgeEvent


class TrustEvaluator:
    """Оценивает уровень доверия на основе события.

    Rules (deterministic, no probabilities):
      - OFFICIAL authority → VERIFIED
      - STRONG authority + CONFLICT_RESOLVED → HIGH
      - Any event with agreement_id → MEDIUM
      - All other → LOW
      - Empty/invalid → UNKNOWN
    """

    @staticmethod
    def evaluate(event: KnowledgeEvent) -> TrustLevel:
        """Evaluate trust level from a knowledge event."""
        if event.authority_level == "official":
            return TrustLevel.VERIFIED
        if event.authority_level == "strong" and event.event_type == "conflict_resolved":
            return TrustLevel.HIGH
        if bool(event.agreement_id):
            return TrustLevel.MEDIUM
        if event.event_type in ("created", "updated"):
            return TrustLevel.LOW
        return TrustLevel.UNKNOWN
