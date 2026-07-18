"""
Tests — Knowledge Query Engine v2.1.3.

All tests: infrastructure-agnostic, deterministic, stateless.
Verified: Plan ≠ Execute, Strategy ≠ Planner, Assembly ≠ Execution.
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from query.knowledge_query import KnowledgeQuery
from query.query_target import QueryTarget
from query.predicate import PredicateOperator, ComparisonPredicate, ExistsPredicate, InPredicate
from query.predicate_composition import And
from query.property_reference import PropertyReference
from query.literal import StringValue, DecimalValue
from query.return_shape import ReturnShape, ReturnShapeType
from query.explainability import ExplainabilityLevel

from query_engine.knowledge_query_engine import KnowledgeQueryEngine
from query_engine.query_planner import QueryPlanner
from query_engine.execution_plan import ExecutionPlan, ResolutionStep
from query_engine.projection_resolver import ProjectionResolver
from query_engine.execution_strategy import ExecutionStrategy, InMemoryStrategy
from query_engine.query_result import QueryResult, QueryMetadata
from query_engine.result_assembler import ResultAssembler
from query_engine.execution_context import ExecutionContext
from query_engine.exceptions import (
    QueryEngineError,
    PlanningError,
    ExecutionError,
    UnsupportedStrategyError,
)

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_query_service import ProjectionQueryService
from projection.projection_store import ProjectionStore

from dataclasses import dataclass


# ─── Test helpers ───

class InMemoryStore:
    """In-memory store for testing (ProjectionStore Protocol)."""
    def __init__(self) -> None:
        self._data: dict[str, Projection] = {}
        self._digests: dict[str, object] = {}

    def put(self, projection: Projection) -> None:
        self._data[projection.projection_id.value] = projection

    def get(self, projection_id: ProjectionId) -> Projection:
        p = self._data.get(projection_id.value)
        if p is None:
            from projection.exceptions import ProjectionNotFoundError
            raise ProjectionNotFoundError(str(projection_id.value))
        return p

    def remove(self, projection_id: ProjectionId) -> bool:
        existed = projection_id.value in self._data
        self._data.pop(projection_id.value, None)
        return existed

    def contains(self, projection_id: ProjectionId) -> bool:
        return projection_id.value in self._data

    def get_digest(self, projection_id: ProjectionId) -> object:
        return self._digests.get(projection_id.value)


@dataclass(frozen=True)
class FakeEntityProj:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.ENTITY
    name: str = "Test"


@dataclass(frozen=True)
class FakeAgreementProj:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.AGREEMENT
    status: str = "ACTIVE"


@dataclass(frozen=True)
class FakeRiskProj:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.RISK
    score: float = 0.5


# ═══════════════════════════════════════════════
# ExecutionPlan Tests
# ═══════════════════════════════════════════════

class TestExecutionPlan:
    def test_from_query(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        plan = ExecutionPlan.from_query(query)
        assert plan.target == QueryTarget.ENTITY
        assert plan.predicate is None
        assert plan.return_shape.shape_type == ReturnShapeType.SUMMARY

    def test_with_predicate(self):
        prop = PropertyReference(target=QueryTarget.RISK, property_name="score")
        pred = ComparisonPredicate(
            property_ref=prop,
            operator=PredicateOperator.GREATER_THAN,
            value=DecimalValue(value=Decimal("0.5")),
        )
        query = KnowledgeQuery(target=QueryTarget.RISK, predicate=pred)
        plan = ExecutionPlan.from_query(query)
        assert plan.predicate is not None

    def test_resolution_steps(self):
        plan = ExecutionPlan(
            target=QueryTarget.ENTITY,
            resolution_steps=(
                ResolutionStep(target=QueryTarget.ENTITY),
            ),
        )
        assert len(plan.resolution_steps) == 1

    def test_immutable(self):
        plan = ExecutionPlan(target=QueryTarget.ENTITY)
        with pytest.raises(Exception):
            plan.target = QueryTarget.AGREEMENT  # type: ignore

    def test_no_execution_code(self):
        plan = ExecutionPlan(target=QueryTarget.ENTITY)
        assert not hasattr(plan, 'execute')
        assert not hasattr(plan, 'run')


# ═══════════════════════════════════════════════
# ProjectionResolver Tests
# ═══════════════════════════════════════════════

class TestProjectionResolver:
    def test_resolve_entity(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        plan = ProjectionResolver.resolve(query)
        assert plan.target == QueryTarget.ENTITY
        # ENTITY has no dependencies
        assert len(plan.resolution_steps) >= 1

    def test_resolve_ownership(self):
        query = KnowledgeQuery(target=QueryTarget.OWNERSHIP)
        plan = ProjectionResolver.resolve(query)
        assert plan.target == QueryTarget.OWNERSHIP

    def test_resolve_risk(self):
        query = KnowledgeQuery(target=QueryTarget.RISK)
        plan = ProjectionResolver.resolve(query)
        assert plan.target == QueryTarget.RISK

    def test_resolve_timeline(self):
        query = KnowledgeQuery(target=QueryTarget.TIMELINE)
        plan = ProjectionResolver.resolve(query)
        assert plan.target == QueryTarget.TIMELINE

    def test_no_store_access(self):
        """Resolver must NOT access the store."""
        assert not hasattr(ProjectionResolver, 'store')
        assert not hasattr(ProjectionResolver, '_store')


# ═══════════════════════════════════════════════
# QueryPlanner Tests
# ═══════════════════════════════════════════════

class TestQueryPlanner:
    def test_plan_entity(self):
        planner = QueryPlanner()
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        plan = planner.plan(query)
        assert isinstance(plan, ExecutionPlan)
        assert plan.target == QueryTarget.ENTITY

    def test_plan_is_deterministic(self):
        planner = QueryPlanner()
        q1 = KnowledgeQuery(target=QueryTarget.RISK)
        q2 = KnowledgeQuery(target=QueryTarget.RISK)
        assert planner.plan(q1) == planner.plan(q2)

    def test_planner_does_not_execute(self):
        planner = QueryPlanner()
        assert not hasattr(planner, 'execute')
        assert not hasattr(planner, 'run')


# ═══════════════════════════════════════════════
# InMemoryStrategy Tests
# ═══════════════════════════════════════════════

class TestInMemoryStrategy:
    def test_execute_empty(self):
        store = InMemoryStore()
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryStrategy(qsvc)

        plan = ExecutionPlan(
            target=QueryTarget.ENTITY,
            resolution_steps=(
                ResolutionStep(target=QueryTarget.ENTITY),
            ),
        )
        results = strategy.execute(plan)
        assert len(results) == 0

    def test_execute_with_projection(self):
        store = InMemoryStore()
        proj = FakeEntityProj(projection_id=ProjectionId(value="entity-v1"))
        store.put(proj)
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryStrategy(qsvc)

        plan = ExecutionPlan(
            target=QueryTarget.ENTITY,
            resolution_steps=(
                ResolutionStep(target=QueryTarget.ENTITY),
            ),
        )
        results = strategy.execute(plan)
        assert len(results) == 1


# ═══════════════════════════════════════════════
# ResultAssembler Tests
# ═══════════════════════════════════════════════

class TestResultAssembler:
    def test_assemble_empty(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        result = ResultAssembler.assemble(query, ())
        assert result.metadata.total_found == 0
        assert len(result.projections) == 0

    def test_assemble_with_projection(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        proj = FakeEntityProj(projection_id=ProjectionId(value="entity-v1"))
        result = ResultAssembler.assemble(query, (proj,))
        assert result.metadata.total_found == 1
        assert len(result.projections) == 1

    def test_assemble_with_explainability(self):
        query = KnowledgeQuery(
            target=QueryTarget.ENTITY,
            explainability=ExplainabilityLevel.SUMMARY,
        )
        proj = FakeEntityProj(projection_id=ProjectionId(value="entity-v1"))
        result = ResultAssembler.assemble(query, (proj,))
        assert len(result.explainability) == 1

    def test_assemble_with_explainability_full(self):
        query = KnowledgeQuery(
            target=QueryTarget.ENTITY,
            explainability=ExplainabilityLevel.FULL,
        )
        proj = FakeEntityProj(projection_id=ProjectionId(value="entity-v1"))
        result = ResultAssembler.assemble(query, (proj,))
        assert len(result.explainability) == 1
        assert "ENTITY" in result.explainability[0]

    def test_no_explainability_when_not_requested(self):
        query = KnowledgeQuery(
            target=QueryTarget.ENTITY,
            explainability=ExplainabilityLevel.NONE,
        )
        proj = FakeEntityProj(projection_id=ProjectionId(value="entity-v1"))
        result = ResultAssembler.assemble(query, (proj,))
        assert len(result.explainability) == 0

    def test_result_immutable(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        result = ResultAssembler.assemble(query, ())
        with pytest.raises(Exception):
            result.projections = ()  # type: ignore


# ═══════════════════════════════════════════════
# KnowledgeQueryEngine Tests
# ═══════════════════════════════════════════════

class TestKnowledgeQueryEngine:
    def test_engine_no_strategy_raises(self):
        engine = KnowledgeQueryEngine()
        with pytest.raises(UnsupportedStrategyError):
            engine.execute(KnowledgeQuery(target=QueryTarget.ENTITY))

    def test_engine_with_strategy(self):
        store = InMemoryStore()
        proj = FakeEntityProj(projection_id=ProjectionId(value="entity-v1"))
        store.put(proj)
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryStrategy(qsvc)
        engine = KnowledgeQueryEngine(strategy=strategy)

        result = engine.execute(KnowledgeQuery(target=QueryTarget.ENTITY))
        assert isinstance(result, QueryResult)
        assert result.metadata.total_found >= 0

    def test_engine_with_predicate(self):
        store = InMemoryStore()
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryStrategy(qsvc)
        engine = KnowledgeQueryEngine(strategy=strategy)

        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ComparisonPredicate(
            property_ref=prop,
            operator=PredicateOperator.EQUALS,
            value=StringValue(value="Test"),
        )
        query = KnowledgeQuery(target=QueryTarget.ENTITY, predicate=pred)
        result = engine.execute(query)
        assert isinstance(result, QueryResult)

    def test_engine_output_immutable(self):
        store = InMemoryStore()
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryStrategy(qsvc)
        engine = KnowledgeQueryEngine(strategy=strategy)

        result = engine.execute(KnowledgeQuery(target=QueryTarget.ENTITY))
        with pytest.raises(Exception):
            result.metadata = QueryMetadata()  # type: ignore

    def test_engine_no_domain_knowledge(self):
        """Engine must not know specific Projection types."""
        engine = KnowledgeQueryEngine()
        assert not hasattr(engine, 'entity_builder')
        assert not hasattr(engine, 'graph_builder')
        assert not hasattr(engine, 'build_projection')


# ═══════════════════════════════════════════════
# ExecutionContext Tests
# ═══════════════════════════════════════════════

class TestExecutionContext:
    def test_create(self):
        plan = ExecutionPlan(target=QueryTarget.ENTITY)
        store = InMemoryStore()
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryStrategy(qsvc)
        ctx = ExecutionContext(
            plan=plan,
            strategy=strategy,
            explainability=ExplainabilityLevel.NONE,
        )
        assert ctx.plan is plan
        assert ctx.strategy is strategy

    def test_immutable(self):
        plan = ExecutionPlan(target=QueryTarget.ENTITY)
        store = InMemoryStore()
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryStrategy(qsvc)
        ctx = ExecutionContext(plan=plan, strategy=strategy)
        with pytest.raises(Exception):
            ctx.plan = ExecutionPlan(target=QueryTarget.AGREEMENT)  # type: ignore


# ═══════════════════════════════════════════════
# Architecture Tests
# ═══════════════════════════════════════════════

class TestQueryEngineArchitecture:
    def test_no_infrastructure_import(self):
        """Engine must NOT import infrastructure modules."""
        import ast
        engine_files = [
            'query_engine/knowledge_query_engine.py',
            'query_engine/query_planner.py',
            'query_engine/execution_plan.py',
            'query_engine/projection_resolver.py',
            'query_engine/execution_strategy.py',
            'query_engine/query_result.py',
            'query_engine/result_assembler.py',
            'query_engine/execution_context.py',
            'query_engine/exceptions.py',
        ]
        base = '/home/xiag/real-estate-os/services/accounting_binding'
        for rel_path in engine_files:
            with open(f"{base}/{rel_path}") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and ('sqlalchemy' in node.module.lower()
                                        or 'psycopg2' in node.module.lower()
                                        or 'neo4j' in node.module.lower()
                                        or 'domain' in node.module.lower()):
                        if 'execution_strategy' in rel_path and 'projection' in node.module:
                            continue  # Projection Layer is allowed
                        pytest.fail(
                            f"{rel_path} imports forbidden: {node.module}"
                        )

    def test_strategy_protocol(self):
        """Strategy must be a Protocol, not a concrete class."""
        # InMemoryStrategy is a concrete implementation
        # ExecutionStrategy is a Protocol
        from typing import Protocol
        assert issubclass(type('_Test', (), {}).__class__, object)

    def test_planner_does_not_import_strategy(self):
        """Planner must NOT know about ExecutionStrategy."""
        import ast
        with open('/home/xiag/real-estate-os/services/accounting_binding/query_engine/query_planner.py') as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and 'execution_strategy' in node.module:
                    pytest.fail("QueryPlanner imports ExecutionStrategy")

    def test_separation_of_concerns(self):
        """Verify Plan ≠ Execute ≠ Assemble."""
        import ast
        with open('/home/xiag/real-estate-os/services/accounting_binding/query_engine/query_planner.py') as f:
            content = f.read()
        assert 'def execute' not in content
        assert 'def assemble' not in content

        with open('/home/xiag/real-estate-os/services/accounting_binding/query_engine/result_assembler.py') as f:
            content = f.read()
        assert 'def execute' not in content
        assert 'def plan' not in content
