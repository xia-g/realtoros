"""
ProvenanceResult, ProvenanceReport — immutable output of provenance building.

NO mutation. NO side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.kg_provenance import KnowledgeProvenance


@dataclass(frozen=True)
class ProvenanceResult:
    """Результат построения происхождения. Immutable."""
    provenance: KnowledgeProvenance
    warnings: tuple[str, ...] = ()

    @property
    def is_success(self) -> bool:
        return len(self.warnings) == 0


@dataclass(frozen=True)
class ProvenanceReport:
    """Отчёт о построении происхождения. Immutable."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sources_created: int = 0
    links_created: int = 0
    chain_length: int = 0
    warnings: tuple[str, ...] = ()
