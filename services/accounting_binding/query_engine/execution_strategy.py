"""
ExecutionStrategy Protocol — abstraction over projection access.

Engine works exclusively through Strategy.
First implementation: InMemoryStrategy.
"""
from __future__ import annotations

from typing import Protocol, Optional

from query.query_target import QueryTarget
from query.predicate import Predicate, ComparisonPredicate, ExistsPredicate, InPredicate
from query.predicate_composition import And, Or, Not, QueryPredicate
from query.return_shape import ReturnShape, ReturnShapeType
from query.explainability import ExplainabilityLevel
from query_engine.execution_plan import ExecutionPlan

from projection.projection import Projection, ProjectionId
from projection.projection_query_service import ProjectionQueryService
from projection.exceptions import ProjectionNotFoundError


class ExecutionStrategy(Protocol):
    """Протокол стратегии исполнения.

    Engine работает исключительно через Strategy.
    """

    def execute(self, plan: ExecutionPlan) -> tuple[Projection, ...]:
        """Execute an ExecutionPlan and return matching projections."""
        ...


class InMemoryStrategy:
    """Стратегия исполнения в памяти.

    Исполняет запрос через Projection Query Service.
    """

    def __init__(self, query_service: ProjectionQueryService) -> None:
        self._query_service = query_service

    def execute(self, plan: ExecutionPlan) -> tuple[Projection, ...]:
        """Execute the plan against the in-memory store.

        Executes resolution steps in order, then filters by predicate.
        """
        # Resolve each step
        resolved: dict[QueryTarget, list[Projection]] = {}
        for step in plan.resolution_steps:
            step_projections = self._resolve_step(step.target)
            resolved[step.target] = list(step_projections)

        # Get target projections
        target_projections = resolved.get(plan.target, [])

        # Filter by predicate
        if plan.predicate is not None:
            # Simple predicate evaluation (extendable)
            filtered = self._filter_projections(target_projections, plan.predicate)
            return tuple(filtered)

        return tuple(target_projections)

    def _resolve_step(self, target: QueryTarget) -> tuple[Projection, ...]:
        """Resolve all projections of a given type.

        In InMemoryStrategy, we get all projections from the store.
        Real strategies (PostgreSQL, Neo4j) will push predicates down.
        """
        # Simple scan — get all projections of this type
        # In a real scenario, this would be index-driven
        projection_id = ProjectionId(value=f"{target.name.lower()}-v1")
        try:
            return (self._query_service.get(projection_id),)
        except ProjectionNotFoundError:
            return ()

    def _filter_projections(
        self,
        projections: list[Projection],
        predicate: QueryPredicate,
    ) -> list[Projection]:
        """Simple in-memory predicate filtering.

        Real strategies push predicates to the storage layer.
        """
        # For composed predicates, recurse
        if isinstance(predicate, And):
            results = projections
            for cond in predicate.conditions:
                results = self._filter_projections(results, cond)
            return results
        elif isinstance(predicate, Or):
            seen: set[int] = set()
            result: list[Projection] = []
            for cond in predicate.conditions:
                for p in self._filter_projections(projections, cond):
                    if id(p) not in seen:
                        seen.add(id(p))
                        result.append(p)
            return result
        elif isinstance(predicate, Not):
            excluded = set(id(p) for p in self._filter_projections(projections, predicate.condition))
            return [p for p in projections if id(p) not in excluded]
        elif isinstance(predicate, ComparisonPredicate):
            # Simplistic evaluation — can't actually access projection fields
            # by name without reflection; real strategies handle this natively
            return projections
        elif isinstance(predicate, ExistsPredicate):
            return projections
        elif isinstance(predicate, InPredicate):
            return projections

        return projections
