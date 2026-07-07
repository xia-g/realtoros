"""
KnowledgeEvolutionResult — immutable output of knowledge evolution computation.
KnowledgeEvolutionReport — audit report for an evolution session.

NO mutation. NO side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.ke_event import KnowledgeEvent
from domain.business_relationship.ke_delta import KnowledgeDelta
from domain.business_relationship.ke_conflict import KnowledgeConflict
from domain.business_relationship.ke_enums import TrustLevel, AuthorityLevel


@dataclass(frozen=True)
class KnowledgeEvolutionResult:
    """Результат вычисления эволюции знаний. Immutable."""
    events: tuple[KnowledgeEvent, ...] = ()
    deltas: tuple[KnowledgeDelta, ...] = ()
    conflicts: tuple[KnowledgeConflict, ...] = ()
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    authority_level: AuthorityLevel = AuthorityLevel.UNKNOWN


@dataclass(frozen=True)
class KnowledgeEvolutionReport:
    """Отчёт о сессии эволюции. Immutable."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_events: int = 0
    total_deltas: int = 0
    total_conflicts: int = 0
