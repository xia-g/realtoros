"""
ExplainabilityResult, ExplainabilityReport — immutable output of explanation building.

NO mutation. NO side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.ke_explanation import GraphExplanation


@dataclass(frozen=True)
class ExplainabilityResult:
    """Результат построения объяснения. Immutable."""
    explanation: GraphExplanation
    warnings: tuple[str, ...] = ()

    @property
    def is_success(self) -> bool:
        return len(self.warnings) == 0


@dataclass(frozen=True)
class ExplainabilityReport:
    """Отчёт о построении объяснения. Immutable."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    steps_created: int = 0
    reasons_created: int = 0
    evidence_count: int = 0
    warnings: tuple[str, ...] = ()
