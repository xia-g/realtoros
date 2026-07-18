"""
Tests — Infrastructure Adapters v2.1.4.

Verifies:
- MemoryProjectionStore matches ProjectionStore Protocol
- InMemoryExecutionStrategy matches ExecutionStrategy Protocol
- ProjectionCodec round-trips correctly
- AdapterConfiguration is immutable
- Composition Root wires correctly
- No business logic leaks into infrastructure
"""
from __future__ import annotations

from dataclasses import dataclass
import pytest

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_query_service import ProjectionQueryService
from projection.exceptions import ProjectionNotFoundError

from infrastructure.memory_store import MemoryProjectionStore
from infrastructure.memory_strategy import InMemoryExecutionStrategy
from infrastructure.projection_codec import ProjectionCodec, ProjectionData
from infrastructure.configuration import AdapterConfiguration, StoreType, StrategyType
from infrastructure.composition_root import (
    ProjectionStoreFactory,
    ExecutionStrategyFactory,
    KnowledgeQueryEngine,
)
from infrastructure.exceptions import (
    StoreError,
    ConfigurationError,
    SerializationError,
)

from query.knowledge_query import KnowledgeQuery
from query.query_target import QueryTarget
from query_engine.execution_plan import ExecutionPlan, ResolutionStep


# ─── Test helpers ───

@dataclass(frozen=True)
class TestProj:
    projection_id: ProjectionId
    projection_type: ProjectionType = ProjectionType.ENTITY
    name: str = "Test"
    score: float = 1.0


# ═══════════════════════════════════════════════
# MemoryProjectionStore Tests
# ═══════════════════════════════════════════════

class TestMemoryProjectionStore:
    def test_put_and_get(self):
        store = MemoryProjectionStore()
        pid = ProjectionId(value="entity-v1")
        proj = TestProj(projection_id=pid)
        store.put(proj)
        assert store.get(pid) == proj

    def test_get_not_found_raises(self):
        store = MemoryProjectionStore()
        with pytest.raises(ProjectionNotFoundError):
            store.get(ProjectionId(value="missing"))

    def test_contains(self):
        store = MemoryProjectionStore()
        pid = ProjectionId(value="x")
        assert not store.contains(pid)
        store.put(TestProj(projection_id=pid))
        assert store.contains(pid)

    def test_remove(self):
        store = MemoryProjectionStore()
        pid = ProjectionId(value="x")
        store.put(TestProj(projection_id=pid))
        assert store.remove(pid)
        assert not store.contains(pid)
        assert not store.remove(pid)

    def test_digest_operations(self):
        store = MemoryProjectionStore()
        pid = ProjectionId(value="x")
        assert store.get_digest(pid) is None

        from projection.projection_digest import ProjectionDigest
        digest = ProjectionDigest(revision_id="r1", revision_number=1, graph_hash="g1", metadata_hash="m1")
        store.put_digest(pid, digest)
        assert store.get_digest(pid) == digest

    def test_count(self):
        store = MemoryProjectionStore()
        assert store.count == 0
        store.put(TestProj(projection_id=ProjectionId(value="a")))
        store.put(TestProj(projection_id=ProjectionId(value="b")))
        assert store.count == 2

    def test_deterministic(self):
        store = MemoryProjectionStore()
        pid = ProjectionId(value="test")
        proj = TestProj(projection_id=pid, name="X")
        store.put(proj)
        assert store.get(pid) == store.get(pid)


# ═══════════════════════════════════════════════
# InMemoryExecutionStrategy Tests
# ═══════════════════════════════════════════════

class TestInMemoryExecutionStrategy:
    def test_execute_empty(self):
        store = MemoryProjectionStore()
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryExecutionStrategy(qsvc)

        plan = ExecutionPlan(
            target=QueryTarget.ENTITY,
            resolution_steps=(ResolutionStep(target=QueryTarget.ENTITY),),
        )
        results = strategy.execute(plan)
        assert len(results) == 0

    def test_execute_with_projection(self):
        store = MemoryProjectionStore()
        proj = TestProj(projection_id=ProjectionId(value="entity-v1"))
        store.put(proj)
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryExecutionStrategy(qsvc)

        plan = ExecutionPlan(
            target=QueryTarget.ENTITY,
            resolution_steps=(ResolutionStep(target=QueryTarget.ENTITY),),
        )
        results = strategy.execute(plan)
        assert len(results) == 1

    def test_execute_deterministic(self):
        store = MemoryProjectionStore()
        proj = TestProj(projection_id=ProjectionId(value="entity-v1"))
        store.put(proj)
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryExecutionStrategy(qsvc)

        plan = ExecutionPlan(
            target=QueryTarget.ENTITY,
            resolution_steps=(ResolutionStep(target=QueryTarget.ENTITY),),
        )
        r1 = strategy.execute(plan)
        r2 = strategy.execute(plan)
        assert r1 == r2


# ═══════════════════════════════════════════════
# ProjectionCodec Tests
# ═══════════════════════════════════════════════

class TestProjectionCodec:
    def test_encode(self):
        pid = ProjectionId(value="entity-v1")
        proj = TestProj(projection_id=pid, name="TestCorp", score=0.95)
        data = ProjectionCodec.encode(proj)
        assert data.projection_id == "entity-v1"
        assert data.projection_type == "ENTITY"
        assert data.fields["name"] == "TestCorp"
        assert data.fields["score"] == 0.95

    def test_round_trip(self):
        pid = ProjectionId(value="entity-v1")
        original = TestProj(projection_id=pid, name="TestCorp")
        data = ProjectionCodec.encode(original)
        decoded = ProjectionCodec.decode(data, TestProj)
        assert decoded.projection_id == original.projection_id
        assert decoded.projection_type == original.projection_type
        assert decoded.name == original.name


# ═══════════════════════════════════════════════
# AdapterConfiguration Tests
# ═══════════════════════════════════════════════

class TestAdapterConfiguration:
    def test_default_config(self):
        config = AdapterConfiguration()
        assert config.store_type == StoreType.MEMORY
        assert config.strategy_type == StrategyType.IN_MEMORY

    def test_custom_config(self):
        config = AdapterConfiguration(
            store_type=StoreType.POSTGRESQL,
            strategy_type=StrategyType.HYBRID,
            connection_string="postgresql://localhost:5432/test",
        )
        assert config.store_type == StoreType.POSTGRESQL
        assert config.connection_string == "postgresql://localhost:5432/test"

    def test_immutable(self):
        config = AdapterConfiguration()
        with pytest.raises(Exception):
            config.store_type = StoreType.POSTGRESQL  # type: ignore


# ═══════════════════════════════════════════════
# Composition Root Tests
# ═══════════════════════════════════════════════

class TestCompositionRoot:
    def test_engine_with_default_config(self):
        engine = KnowledgeQueryEngine()
        result = engine.execute(KnowledgeQuery(target=QueryTarget.ENTITY))
        assert result.metadata.total_found == 0

    def test_engine_with_custom_store(self):
        store = MemoryProjectionStore()
        proj = TestProj(projection_id=ProjectionId(value="entity-v1"))
        store.put(proj)

        from projection.projection_query_service import ProjectionQueryService
        qsvc = ProjectionQueryService(store)

        engine = KnowledgeQueryEngine(
            config=AdapterConfiguration(),
            store=store,
            query_service=qsvc,
        )
        result = engine.execute(KnowledgeQuery(target=QueryTarget.ENTITY))
        assert result.metadata.total_found == 1


# ═══════════════════════════════════════════════
# Architecture Tests
# ═══════════════════════════════════════════════

class TestInfrastructureArchitecture:
    def test_no_domain_import(self):
        """Infrastructure must NOT import Domain modules directly."""
        import ast
        infra_files = [
            'infrastructure/memory_store.py',
            'infrastructure/memory_strategy.py',
            'infrastructure/projection_codec.py',
            'infrastructure/configuration.py',
            'infrastructure/composition_root.py',
            'infrastructure/exceptions.py',
        ]
        base = '/home/xiag/real-estate-os/services/accounting_binding'
        for rel_path in infra_files:
            with open(f"{base}/{rel_path}") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and 'domain' in node.module:
                        # Only composition_root is allowed higher-level imports
                        if 'composition_root' in rel_path:
                            continue
                        pytest.fail(f"{rel_path} imports Domain: {node.module}")

    def test_memory_store_matches_protocol(self):
        """MemoryProjectionStore must implement all ProjectionStore methods."""
        store = MemoryProjectionStore()
        assert hasattr(store, 'put')
        assert hasattr(store, 'get')
        assert hasattr(store, 'remove')
        assert hasattr(store, 'contains')
        assert hasattr(store, 'get_digest')

    def test_strategy_matches_protocol(self):
        """InMemoryExecutionStrategy must implement execute."""
        store = MemoryProjectionStore()
        qsvc = ProjectionQueryService(store)
        strategy = InMemoryExecutionStrategy(qsvc)
        assert hasattr(strategy, 'execute')

    def test_no_business_logic(self):
        """Infrastructure must not contain business logic methods."""
        store = MemoryProjectionStore()
        assert not hasattr(store, 'build')
        assert not hasattr(store, 'plan')
        assert not hasattr(store, 'validate')
        assert not hasattr(store, 'resolve')
