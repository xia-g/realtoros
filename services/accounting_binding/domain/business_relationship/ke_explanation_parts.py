"""
ExplanationReason, ExplanationEvidence — immutable parts of an explanation.

Pure data. No computation.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.ke_explanation_reason import ExplanationReasonType


@dataclass(frozen=True)
class ExplanationReason:
    """Причина объяснения. Immutable."""
    reason_type: ExplanationReasonType
    summary: str = ""
    confidence: float = 1.0
    related_domain_id: str = ""


@dataclass(frozen=True)
class ExplanationEvidence:
    """Доказательство объяснения. Immutable."""
    source_type: str = ""
    source_id: str = ""
    description: str = ""
    confidence: float = 1.0
