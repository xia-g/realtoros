"""
GraphBuildResult, GraphBuildReport — immutable output of graph building.

NO mutation. NO side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.kg_graph import KnowledgeGraph


@dataclass(frozen=True)
class GraphBuildResult:
    """Результат построения графа. Immutable."""
    graph: KnowledgeGraph
    warnings: tuple[str, ...] = ()

    @property
    def is_success(self) -> bool:
        return len(self.warnings) == 0


@dataclass(frozen=True)
class GraphBuildReport:
    """Отчёт о построении графа. Immutable."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    nodes_created: int = 0
    edges_created: int = 0
    warnings: tuple[str, ...] = ()
