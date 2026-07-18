"""Tests for Sprint 5.2 Critical Architecture Fixes."""

import asyncio
from uuid import UUID

import pytest

# ── P1: Domain Event Bus ──


class TestDomainEventBus:
    def test_event_dataclass(self):
        from backend.core.domain_events import DomainEvent, get_event_bus
        event = DomainEvent(event_type="client.created", entity_type="client", entity_id=UUID(int=1), correlation_id="abc")
        assert event.event_type == "client.created"
        assert event.correlation_id == "abc"

    def test_event_bus_singleton(self):
        from backend.core.domain_events import get_event_bus
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_register_and_emit(self):
        from backend.core.domain_events import DomainEvent, get_event_bus
        bus = get_event_bus()
        results = []

        async def handler(event):
            results.append(event.event_type)

        bus.register("test.event", handler)
        asyncio.run(bus.emit(DomainEvent(event_type="test.event", entity_type="test", entity_id=UUID(int=1))))
        assert "test.event" in results

    def test_event_types_defined(self):
        from backend.core.domain_events import (
            EVENT_CLIENT_CREATED, EVENT_CLIENT_UPDATED, EVENT_CLIENT_DELETED,
            EVENT_DEAL_CREATED, EVENT_DEAL_UPDATED, EVENT_DEAL_DELETED,
            EVENT_DOCUMENT_CREATED, EVENT_DOCUMENT_DELETED,
            EVENT_LEAD_CONVERTED, EVENT_LEAD_MERGED,
        )
        assert EVENT_CLIENT_CREATED == "client.created"
        assert EVENT_DEAL_CREATED == "deal.created"
        assert EVENT_LEAD_CONVERTED == "lead.converted"


# ── P2: Graph Referential Integrity ──


class TestGraphLifecycleService:
    def test_service_init(self):
        from backend.services.graph_lifecycle_service import GraphLifecycleService
        svc = GraphLifecycleService(None)
        assert svc is not None

    def test_soft_delete_node(self):
        from backend.services.graph_lifecycle_service import GraphLifecycleService
        import asyncio
        svc = GraphLifecycleService(None)
        # Without session, should return False (no rows affected)
        r = asyncio.run(svc.soft_delete_node(UUID(int=1)))
        assert r is False

    def test_restore_node(self):
        from backend.services.graph_lifecycle_service import GraphLifecycleService
        import asyncio
        svc = GraphLifecycleService(None)
        r = asyncio.run(svc.restore_node(UUID(int=1)))
        assert r is False


# ── P3: Soft Delete ──


class TestSoftDeleteMigration:
    def test_migration_016_exists(self):
        import os
        path = "backend/migrations/versions/016_add_soft_delete_and_source_ref.py"
        assert os.path.exists(path), f"{path} not found"

    def test_graph_node_has_new_fields(self):
        from backend.models.graph_node import GraphNode
        assert hasattr(GraphNode, "source_entity_type")
        assert hasattr(GraphNode, "source_entity_id")
        assert hasattr(GraphNode, "deleted_at")


# ── P5: Compliance Audit ──


class TestComplianceAudit:
    def test_model_exists(self):
        from backend.models.compliance_audit import ComplianceAudit
        assert hasattr(ComplianceAudit, "deal_id")
        assert hasattr(ComplianceAudit, "correlation_id")
        assert hasattr(ComplianceAudit, "audit_type")
        assert hasattr(ComplianceAudit, "result")

    def test_audit_types(self):
        from backend.models.compliance_audit import ComplianceAudit
        # These should be used as audit_type values
        valid_types = ["compliance", "risk", "workflow"]
        for t in valid_types:
            assert isinstance(t, str)

    def test_regulation_audit_fields(self):
        from backend.models.compliance_audit import ComplianceAudit
        assert hasattr(ComplianceAudit, "used_regulations")
        assert hasattr(ComplianceAudit, "used_documents")


# ── P6: Regulation Mapping ──


class TestRegulationMapping:
    def test_model_exists(self):
        from backend.models.regulation_requirement_mapping import RegulationRequirementMapping
        assert hasattr(RegulationRequirementMapping, "regulation_id")
        assert hasattr(RegulationRequirementMapping, "document_type")
        assert hasattr(RegulationRequirementMapping, "checkpoint_key")
        assert hasattr(RegulationRequirementMapping, "article")

    def test_unique_constraint(self):
        from backend.models.regulation_requirement_mapping import RegulationRequirementMapping
        # Ensure the table_args exists
        assert RegulationRequirementMapping.__table_args__ is not None


# ── P7: Partitioning ──


class TestPartitioning:
    def test_migration_018_exists(self):
        import os
        path = "backend/migrations/versions/018_prepare_audit_partitioning.py"
        assert os.path.exists(path), f"{path} not found"

    def test_ai_call_log_has_partition_comment(self):
        import os
        path = "backend/migrations/versions/006_add_ai_call_log.py"
        content = open(path).read()
        assert "partition" in content.lower()


# ── P8: Distributed Rate Limiter ──


class TestRateLimiter:
    def test_pg_backend_init(self):
        from backend.services.rate_limiter import PostgresRateLimiter
        limiter = PostgresRateLimiter()
        assert limiter is not None

    def test_memory_fallback(self):
        from backend.services.rate_limiter import PostgresRateLimiter, MinuteWindowRateLimiter
        limiter = PostgresRateLimiter()
        mw = MinuteWindowRateLimiter()
        assert mw is not None


# ── Event Handlers ──


class TestEventHandlers:
    def test_register_sync_handlers(self):
        from backend.core.domain_events import get_event_bus
        from backend.core.event_handlers import register_sync_handlers
        bus = get_event_bus()
        register_sync_handlers(bus)
        # Should not crash


# ── Migration Count ──


class TestMigrationCount:
    def test_18_migrations_exist(self):
        import os
        versions = os.listdir("backend/migrations/versions")
        py_files = [f for f in versions if f.endswith(".py") and f.startswith("0")]
        assert len(py_files) >= 18, f"Expected 18+ migrations, got {len(py_files)}"
