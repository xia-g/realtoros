"""
KnowledgeRevisionResult + KnowledgeRevisionReport — build result.

Immutable. No logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.knowledge_revision import KnowledgeRevision


@dataclass(frozen=True)
class KnowledgeRevisionReport:
    """Агрегированная информация о построенной ревизии. Immutable."""
    revision_number: int = 0
    nodes_total: int = 0
    edges_total: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeRevisionResult:
    """Результат построения ревизии. Immutable."""
    revision: KnowledgeRevision
    report: KnowledgeRevisionReport
    warnings: tuple[str, ...] = ()
