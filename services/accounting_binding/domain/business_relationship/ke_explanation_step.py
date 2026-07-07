"""
ExplanationStep — one step in a knowledge explanation.

Immutable. No behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.ke_explanation_parts import ExplanationReason, ExplanationEvidence


@dataclass(frozen=True)
class ExplanationStep:
    """Шаг объяснения. Immutable."""
    step_number: int = 0
    summary: str = ""
    reasons: tuple[ExplanationReason, ...] = ()
    evidence: tuple[ExplanationEvidence, ...] = ()
