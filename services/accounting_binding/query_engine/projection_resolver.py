"""
ProjectionResolver — determines which Projections are needed for a query.

Does NOT access Store. Only determines dependencies.
"""
from __future__ import annotations

from query.knowledge_query import KnowledgeQuery
from query.query_target import QueryTarget
from query_engine.execution_plan import ExecutionPlan, ResolutionStep

# Dependency map: which projections depend on which
_DEPENDENCY_MAP: dict[QueryTarget, tuple[QueryTarget, ...]] = {
    QueryTarget.ENTITY: (),
    QueryTarget.AGREEMENT: (QueryTarget.ENTITY,),
    QueryTarget.OWNERSHIP: (QueryTarget.ENTITY,),
    QueryTarget.TIMELINE: (QueryTarget.ENTITY, QueryTarget.AGREEMENT),
    QueryTarget.GRAPH: (QueryTarget.ENTITY, QueryTarget.AGREEMENT),
    QueryTarget.PROVENANCE: (QueryTarget.GRAPH,),
    QueryTarget.RISK: (QueryTarget.ENTITY, QueryTarget.OWNERSHIP),
}


class ProjectionResolver:
    """Определяет, какие Projection необходимы для выполнения запроса.

    Не обращается к Store. Только определяет зависимости.
    """

    @staticmethod
    def resolve(query: KnowledgeQuery) -> ExecutionPlan:
        """Resolve required projections for a query.

        Returns an ExecutionPlan with full resolution steps.
        """
        target = query.target
        dependencies = _DEPENDENCY_MAP.get(target, ())

        # Build resolution steps: resolve dependencies first, then target
        steps: list[ResolutionStep] = []
        resolved: set[QueryTarget] = set()

        def _add_deps(t: QueryTarget) -> None:
            deps = _DEPENDENCY_MAP.get(t, ())
            for dep in deps:
                if dep not in resolved:
                    _add_deps(dep)
            if t not in resolved:
                step_deps = tuple(d for d in _DEPENDENCY_MAP.get(t, ()) if d in resolved)
                steps.append(ResolutionStep(target=t, depends_on=step_deps))
                resolved.add(t)

        _add_deps(target)

        plan = ExecutionPlan.from_query(query)
        return ExecutionPlan(
            target=plan.target,
            predicate=plan.predicate,
            return_shape=plan.return_shape,
            explainability=plan.explainability,
            resolution_steps=tuple(steps),
        )
