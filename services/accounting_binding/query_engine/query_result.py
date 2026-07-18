"""
QueryResult — immutable result of query execution.

Includes: found projections, explainability (if requested),
metadata, minimal statistics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from projection.projection import Projection
from query.knowledge_query import KnowledgeQuery
from query.explainability import ExplainabilityLevel


@dataclass(frozen=True)
class QueryMetadata:
    """Метаданные выполнения запроса."""
    total_found: int = 0
    execution_time_ms: float = 0.0
    resolve_order: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryResult:
    """Immutable результат выполнения запроса.

    Содержит найденные Projection, Explainability,
    Metadata и минимальную статистику.
    """
    query: KnowledgeQuery
    projections: tuple[Projection, ...] = ()
    explainability: tuple[str, ...] = ()
    metadata: QueryMetadata = QueryMetadata()
