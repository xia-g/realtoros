"""
QueryPlanner — transforms KnowledgeQuery → ExecutionPlan.

Fully deterministic. Plans nothing but the execution.
Does NOT execute.
"""
from __future__ import annotations

from query.knowledge_query import KnowledgeQuery
from query_engine.execution_plan import ExecutionPlan
from query_engine.projection_resolver import ProjectionResolver


class QueryPlanner:
    """Преобразует KnowledgeQuery → ExecutionPlan.

    Полностью детерминирован.
    Ничего не исполняет.
    """

    def __init__(self) -> None:
        self._resolver = ProjectionResolver()

    def plan(self, query: KnowledgeQuery) -> ExecutionPlan:
        """Create an execution plan from a query.

        Steps:
        1. Validate query structure
        2. Resolve required projections
        3. Build execution plan

        Returns:
            Immutable ExecutionPlan
        """
        # Resolve projections and build full plan
        plan = self._resolver.resolve(query)
        return plan
