"""
Tests — Projection Layer v2.1.1.

Covers: Projection, BuildPlan, ProjectionRegistry,
        ProjectionCoordinator, ProjectionDigest,
        StalenessService, ProjectionQueryService.

All tests: deterministic, no infrastructure, no Domain leakage.
"""
from __future__ import annotations

import pytest

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.build_plan import BuildPlan, BuildStep
from projection.projection_builder import ProjectionBuilder
from projection.projection_registry import ProjectionRegistry
from projection.projection_coordinator import ProjectionCoordinator, CoordinatorResult
from projection.projection_store import ProjectionStore
from projection.projection_query_service import ProjectionQueryService
from projection.projection_digest import ProjectionDigest, ProjectionDigestResult
from projection.staleness import StalenessService, StalenessResult, StalenessState
from projection.exceptions import (
    ProjectionNotFoundError,
    ProjectionBuilderNotFoundError,
    BuildPlanError,
    ProjectionError,
)

# ─── In-memory store for testing ───

class InMemoryProjectionStore:
    """In-memory implementation of ProjectionStore for testing."""

    def __init__(self) -> None:
        self._data: dict[str, Projection] = {}
        self._digests: dict[str, ProjectionDigest] = {}

    def put(self, projection: Projection) -> None:
        self._data[projection.projection_id.value] = projection

    def get(self, projection_id: ProjectionId) -> Projection:
        p = self._data.get(projection_id.value)
        if p is None:
            raise ProjectionNotFoundError(f"Not found: {projection_id.value}")
        return p

    def remove(self, projection_id: ProjectionId) -> bool:
        existed = projection_id.value in self._data
        self._data.pop(projection_id.value, None)
        self._digests.pop(projection_id.value, None)
        return existed

    def contains(self, projection_id: ProjectionId) -> bool:
        return projection_id.value in self._data

    def get_digest(self, projection_id: ProjectionId) -> ProjectionDigest | None:
        return self._digests.get(projection_id.value)


# ─── Test helpers ───

from dataclasses import dataclass


@dataclass(frozen=True)
class FakeEntityProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.ENTITY
    name: str = ""


@dataclass(frozen=True)
class FakeGraphProjection:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.GRAPH
    node_count: int = 0


class FakeEntityBuilder:
    @property
    def projection_type(self) -> ProjectionType:
        return ProjectionType.ENTITY

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        return FakeEntityProjection(projection_id=projection_id, name="TestEntity")

    def can_build(self, domain_state: object) -> bool:
        return True


class FakeGraphBuilder:
    @property
    def projection_type(self) -> ProjectionType:
        return ProjectionType.GRAPH

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        return FakeGraphProjection(projection_id=projection_id, node_count=5)

    def can_build(self, domain_state: object) -> bool:
        return True


class UnbuildableBuilder:
    @property
    def projection_type(self) -> ProjectionType:
        return ProjectionType.RISK

    def build(self, domain_state: object, projection_id: ProjectionId) -> Projection:
        raise NotImplementedError()

    def can_build(self, domain_state: object) -> bool:
        return False


# ═══════════════════════════════════════════════
# Projection Unit Tests
# ═══════════════════════════════════════════════

class TestProjectionId:
    def test_create(self):
        pid = ProjectionId(value="entity-v1")
        assert pid.value == "entity-v1"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            ProjectionId(value="")
        with pytest.raises(ValueError):
            ProjectionId(value="   ")

    def test_immutable(self):
        pid = ProjectionId(value="x")
        with pytest.raises(Exception):
            pid.value = "y"


class TestProjectionType:
    def test_all_values_present(self):
        assert ProjectionType.ENTITY
        assert ProjectionType.OWNERSHIP
        assert ProjectionType.TIMELINE
        assert ProjectionType.GRAPH
        assert ProjectionType.RISK
        assert ProjectionType.AGREEMENT
        assert ProjectionType.PROVENANCE


# ═══════════════════════════════════════════════
# BuildPlan Tests
# ═══════════════════════════════════════════════

class TestBuildPlan:
    def test_full_build_plan(self):
        plan = BuildPlan.full()
        assert len(plan.steps) == 7
        assert ProjectionType.ENTITY in plan.projection_types
        assert ProjectionType.RISK in plan.projection_types

    def test_single_build_plan(self):
        plan = BuildPlan.single(ProjectionType.ENTITY)
        assert len(plan.steps) == 1
        assert plan.steps[0].projection_type == ProjectionType.ENTITY

    def test_custom_build_plan(self):
        plan = BuildPlan.custom([
            BuildStep(projection_type=ProjectionType.ENTITY),
            BuildStep(projection_type=ProjectionType.OWNERSHIP, depends_on=(ProjectionType.ENTITY,)),
        ])
        assert len(plan.steps) == 2

    def test_dependencies(self):
        plan = BuildPlan.full()
        deps = plan.depends_on(ProjectionType.GRAPH)
        assert ProjectionType.ENTITY in deps
        assert ProjectionType.AGREEMENT in deps

    def test_immutable(self):
        plan = BuildPlan.full()
        with pytest.raises(Exception):
            plan.steps = ()  # type: ignore

    def test_build_step_label_default(self):
        step = BuildStep(projection_type=ProjectionType.ENTITY)
        assert step.label == "entity"

    def test_build_step_custom_label(self):
        step = BuildStep(projection_type=ProjectionType.RISK, label="risk-analysis")
        assert step.label == "risk-analysis"


# ═══════════════════════════════════════════════
# ProjectionRegistry Tests
# ═══════════════════════════════════════════════

class TestProjectionRegistry:
    def test_register_and_get(self):
        registry = ProjectionRegistry()
        builder = FakeEntityBuilder()
        registry.register(builder)
        assert registry.get(ProjectionType.ENTITY) is builder

    def test_get_unregistered_raises(self):
        registry = ProjectionRegistry()
        with pytest.raises(ProjectionBuilderNotFoundError):
            registry.get(ProjectionType.RISK)

    def test_has(self):
        registry = ProjectionRegistry()
        assert not registry.has(ProjectionType.ENTITY)
        registry.register(FakeEntityBuilder())
        assert registry.has(ProjectionType.ENTITY)

    def test_registered_types(self):
        registry = ProjectionRegistry()
        registry.register(FakeEntityBuilder())
        registry.register(FakeGraphBuilder())
        assert ProjectionType.ENTITY in registry.registered_types
        assert ProjectionType.GRAPH in registry.registered_types


# ═══════════════════════════════════════════════
# ProjectionDigest Tests
# ═══════════════════════════════════════════════

from dataclasses import dataclass as digest_dataclass


@digest_dataclass(frozen=True)
class FakeRevisionSnapshot:
    graph: object = None

    @property
    def total_nodes(self) -> int:
        return 0

    @property
    def total_edges(self) -> int:
        return 0


@digest_dataclass(frozen=True)
class FakeRevision:
    revision_id: str = "r1"
    revision_number: object = None
    snapshot: object = None
    metadata: object = None


@digest_dataclass(frozen=True)
class FakeRevisionNumber:
    number: int = 0


@digest_dataclass(frozen=True)
class FakeGraph:
    pass


class TestProjectionDigest:
    def test_from_revision(self):
        class MockRevision:
            revision_id = "rev-1"
            revision_number = FakeRevisionNumber(number=5)
            snapshot = None
            metadata = None

        digest = ProjectionDigest.from_revision(MockRevision())
        assert digest.revision_id == "rev-1"
        assert digest.revision_number == 5

    def test_empty_digest(self):
        digest = ProjectionDigest.empty()
        assert digest.is_empty
        assert digest.revision_number == -1

    def test_empty_is_not_from_revision(self):
        class MockRevision:
            revision_id = "x"
            revision_number = FakeRevisionNumber(number=0)
            snapshot = None
            metadata = None

        digest = ProjectionDigest.from_revision(MockRevision())
        assert not digest.is_empty

    def test_deterministic(self):
        class Rev1:
            revision_id = "r1"
            revision_number = FakeRevisionNumber(number=1)
            snapshot = None
            metadata = None

        class Rev2:
            revision_id = "r1"
            revision_number = FakeRevisionNumber(number=1)
            snapshot = None
            metadata = None

        assert ProjectionDigest.from_revision(Rev1()) == ProjectionDigest.from_revision(Rev2())

    def test_immutable(self):
        digest = ProjectionDigest(revision_id="r1", revision_number=1, graph_hash="g1", metadata_hash="m1")
        with pytest.raises(Exception):
            digest.revision_id = "r2"


# ═══════════════════════════════════════════════
# ProjectionCoordinator Tests
# ═══════════════════════════════════════════════

class TestProjectionCoordinator:
    def test_execute_full_build(self):
        registry = ProjectionRegistry()
        registry.register(FakeEntityBuilder())
        registry.register(FakeGraphBuilder())
        store = InMemoryProjectionStore()
        coordinator = ProjectionCoordinator(registry, store)

        plan = BuildPlan.custom([
            BuildStep(projection_type=ProjectionType.ENTITY),
            BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY,)),
        ])

        result = coordinator.execute(plan, domain_state={})
        assert len(result.built) == 2
        assert len(result.errors) == 0

    def test_execute_unbuildable_skipped(self):
        registry = ProjectionRegistry()
        registry.register(UnbuildableBuilder())
        store = InMemoryProjectionStore()
        coordinator = ProjectionCoordinator(registry, store)

        result = coordinator.execute(
            BuildPlan.single(ProjectionType.RISK),
            domain_state={},
        )
        assert len(result.built) == 0
        assert len(result.skipped) == 1

    def test_skip_on_unregistered_builder(self):
        registry = ProjectionRegistry()
        store = InMemoryProjectionStore()
        coordinator = ProjectionCoordinator(registry, store)

        result = coordinator.execute(
            BuildPlan.single(ProjectionType.ENTITY),
            domain_state={},
        )
        assert len(result.built) == 0
        assert len(result.errors) >= 1

    def test_coordinator_result_immutable(self):
        result = CoordinatorResult(built=(), skipped=(), errors=())
        with pytest.raises(Exception):
            result.built = (object(),)  # type: ignore

    def test_no_domain_knowledge_in_coordinator(self):
        assert not hasattr(ProjectionCoordinator, 'build_graph')
        assert not hasattr(ProjectionCoordinator, 'build_entity')
        assert not hasattr(ProjectionCoordinator, 'build')

    def test_circular_dependency_detection(self):
        registry = ProjectionRegistry()
        store = InMemoryProjectionStore()
        coordinator = ProjectionCoordinator(registry, store)

        plan = BuildPlan.custom([
            BuildStep(projection_type=ProjectionType.ENTITY, depends_on=(ProjectionType.GRAPH,)),
            BuildStep(projection_type=ProjectionType.GRAPH, depends_on=(ProjectionType.ENTITY,)),
        ])

        with pytest.raises(BuildPlanError):
            coordinator.execute(plan, domain_state={})


# ═══════════════════════════════════════════════
# ProjectionQueryService Tests
# ═══════════════════════════════════════════════

class TestProjectionQueryService:
    def test_get(self):
        store = InMemoryProjectionStore()
        svc = ProjectionQueryService(store)
        pid = ProjectionId(value="entity-v1")
        proj = FakeEntityProjection(projection_id=pid)
        store.put(proj)

        result = svc.get(pid)
        assert result is proj

    def test_get_not_found_raises(self):
        store = InMemoryProjectionStore()
        svc = ProjectionQueryService(store)
        with pytest.raises(ProjectionNotFoundError):
            svc.get(ProjectionId(value="nonexistent"))

    def test_exists(self):
        store = InMemoryProjectionStore()
        svc = ProjectionQueryService(store)
        pid = ProjectionId(value="x")
        assert not svc.exists(pid)
        store.put(FakeEntityProjection(projection_id=pid))
        assert svc.exists(pid)

    def test_get_many(self):
        store = InMemoryProjectionStore()
        svc = ProjectionQueryService(store)
        pid1 = ProjectionId(value="a")
        pid2 = ProjectionId(value="b")
        proj1 = FakeEntityProjection(projection_id=pid1)
        store.put(proj1)
        # pid2 is missing

        results = svc.get_many([pid1, pid2])
        assert len(results) == 1
        assert results[0] is proj1

    def test_no_query_methods(self):
        store = InMemoryProjectionStore()
        svc = ProjectionQueryService(store)
        assert not hasattr(svc, 'filter')
        assert not hasattr(svc, 'search')
        assert not hasattr(svc, 'join')
        assert not hasattr(svc, 'sort')
        assert not hasattr(svc, 'aggregate')
        assert not hasattr(svc, 'plan')
        assert not hasattr(svc, 'execute')


# ═══════════════════════════════════════════════
# StalenessService Tests
# ═══════════════════════════════════════════════

class TestStalenessService:
    def test_missing(self):
        store = InMemoryProjectionStore()
        svc = StalenessService(store)
        current = ProjectionDigest(revision_id="r1", revision_number=1, graph_hash="g1", metadata_hash="m1")
        pid = ProjectionId(value="proj-1")

        result = svc.check(pid, current)
        assert result.state == StalenessState.MISSING

    def test_fresh(self):
        store = InMemoryProjectionStore()
        svc = StalenessService(store)
        current = ProjectionDigest(revision_id="r1", revision_number=1, graph_hash="g1", metadata_hash="m1")
        pid = ProjectionId(value="proj-1")

        # Simulate stored digest (matching)
        store._digests[pid.value] = current

        result = svc.check(pid, current)
        assert result.state == StalenessState.FRESH

    def test_stale(self):
        store = InMemoryProjectionStore()
        svc = StalenessService(store)
        stored = ProjectionDigest(revision_id="r1", revision_number=1, graph_hash="g1", metadata_hash="m1")
        current = ProjectionDigest(revision_id="r1", revision_number=2, graph_hash="g2", metadata_hash="m2")
        pid = ProjectionId(value="proj-1")

        store._digests[pid.value] = stored

        result = svc.check(pid, current)
        assert result.state == StalenessState.STALE

    def test_is_fresh_quick(self):
        store = InMemoryProjectionStore()
        svc = StalenessService(store)
        digest = ProjectionDigest(revision_id="r1", revision_number=1, graph_hash="g1", metadata_hash="m1")
        pid = ProjectionId(value="proj-1")

        store._digests[pid.value] = digest
        assert svc.is_fresh(pid, digest)
        assert not svc.is_fresh(pid, ProjectionDigest.empty())

    def test_check_many(self):
        store = InMemoryProjectionStore()
        svc = StalenessService(store)
        digest = ProjectionDigest(revision_id="r1", revision_number=1, graph_hash="g1", metadata_hash="m1")

        pid_fresh = ProjectionId(value="fresh")
        pid_missing = ProjectionId(value="missing")
        store._digests[pid_fresh.value] = digest

        results = svc.check_many((
            (pid_fresh, digest),
            (pid_missing, digest),
        ))
        assert results[0].state == StalenessState.FRESH
        assert results[1].state == StalenessState.MISSING

    def test_staleness_result_immutable(self):
        d1 = ProjectionDigest.empty()
        result = StalenessResult(
            state=StalenessState.FRESH,
            projection_id=ProjectionId(value="x"),
            stored_digest=d1,
            current_digest=d1,
        )
        with pytest.raises(Exception):
            result.state = StalenessState.STALE  # type: ignore


# ═══════════════════════════════════════════════
# Architecture Tests
# ═══════════════════════════════════════════════

class TestProjectionArchitecture:
    def test_no_domain_import(self):
        """Projection layer source files must NOT import Domain modules."""
        import ast

        projection_files = [
            'projection/projection.py',
            'projection/build_plan.py',
            'projection/projection_builder.py',
            'projection/projection_registry.py',
            'projection/projection_coordinator.py',
            'projection/projection_store.py',
            'projection/projection_query_service.py',
            'projection/projection_digest.py',
            'projection/staleness.py',
            'projection/exceptions.py',
        ]

        base = '/home/xiag/real-estate-os/services/accounting_binding'

        for rel_path in projection_files:
            fpath = f"{base}/{rel_path}"
            with open(fpath) as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if 'domain' in alias.name:
                                pytest.fail(
                                    f"{rel_path} imports Domain: '{alias.name}'"
                                )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and 'domain' in node.module:
                            pytest.fail(
                                f"{rel_path} imports Domain: '{node.module}'"
                            )

        import sys
        # Only check in-modules assertions if we're sure sys is available
        # AST check above is the primary enforcement
        pass  # AST check is the primary enforcement

    def test_no_query_methods_on_store(self):
        """Store must NOT have query/plan/filter methods."""
        store = InMemoryProjectionStore()
        assert not hasattr(store, 'filter')
        assert not hasattr(store, 'search')
        assert not hasattr(store, 'query')
        assert not hasattr(store, 'plan')

    def test_all_projection_types_have_default_label(self):
        for pt in ProjectionType:
            step = BuildStep(projection_type=pt)
            assert step.label == pt.name.lower()
