"""
KnowledgeQueryEngine — main facade of the Query Engine layer.

Single public entry point. Accepts KnowledgeQuery, returns QueryResult.
Knows nothing about specific Projections.
Only coordinates other services.
"""
from __future__ import annotations

from typing import Optional

from query.knowledge_query import KnowledgeQuery
from query.query_validation import QueryValidator
from query_engine.query_planner import QueryPlanner
from query_engine.execution_plan import ExecutionPlan
from query_engine.execution_context import ExecutionContext
from query_engine.execution_strategy import ExecutionStrategy, InMemoryStrategy
from query_engine.result_assembler import ResultAssembler
from query_engine.query_result import QueryResult
from query_engine.exceptions import PlanningError, ExecutionError, UnsupportedStrategyError

from projection.projection_query_service import ProjectionQueryService


class KnowledgeQueryEngine:
    """Главный фасад слоя Query Engine.

    Единственная публичная точка входа.
    Принимает KnowledgeQuery, возвращает QueryResult.
    Ничего не знает о конкретных Projection.
    Только координирует остальные сервисы.
    """

    def __init__(
        self,
        strategy: Optional[ExecutionStrategy] = None,
    ) -> None:
        self._planner = QueryPlanner()
        self._assembler = ResultAssembler()
        self._strategy = strategy

    def execute(self, query: KnowledgeQuery) -> QueryResult:
        """Execute a KnowledgeQuery and return QueryResult.

        Pipeline:
        1. Validate query (via QueryValidator)
        2. Plan execution (via QueryPlanner)
        3. Execute plan (via ExecutionStrategy)
        4. Assemble result (via ResultAssembler)
        """
        # 1. Validate
        QueryValidator.validate(query)

        # 2. Plan
        plan = self._planner.plan(query)

        # 3. Execute
        if self._strategy is None:
            raise UnsupportedStrategyError("No execution strategy configured")

        projections = self._strategy.execute(plan)

        # 4. Assemble
        result = self._assembler.assemble(query, projections)

        return result
