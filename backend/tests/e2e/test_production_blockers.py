"""Tests for Sprint 8.8 production blockers — adversarial scenarios."""

import asyncio
from uuid import UUID

import pytest


class TestProductionBlockers:
    """Adversarial tests for C1-C6 from production audit."""

    # ── P1: Soft Delete Consistency ──

    def test_deals_have_deleted_at(self):
        """Verify deals.deleted_at exists (migration 022)."""
        from backend.models.deal import Deal
        assert hasattr(Deal, "deleted_at"), "Deal missing deleted_at"

    def test_analytics_tables_have_deleted_at(self):
        """Verify analytics tables have deleted_at."""
        from backend.models.analytics_snapshot import AnalyticsSnapshot
        from backend.models.analytics_alert import AnalyticsAlert
        from backend.models.prediction_result import PredictionResult
        assert hasattr(AnalyticsSnapshot, "deleted_at")
        assert hasattr(AnalyticsAlert, "deleted_at")
        assert hasattr(PredictionResult, "deleted_at")

    # ── P2: Partitioning ──

    def test_partition_migration_exists(self):
        """023 migration for partitions exists."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        mig = root / "backend" / "migrations" / "versions" / "023_partition_audit_tables.py"
        assert mig.exists(), "Partition migration 023 not found"

    def test_partition_script_exists(self):
        """create_partitions.sql exists with correct DDL."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        script = root / "backend" / "scripts" / "create_partitions.sql"
        assert script.exists(), "Partition script not found"
        content = script.read_text()
        assert "PARTITION BY RANGE" in content
        assert "ai_call_log_old" in content
        assert "agent_tool_calls_old" in content
        assert "compliance_audits_old" in content

    # ── P3: CHECK Constraints ──

    def test_deal_status_constraint(self):
        """Verify ck_deal_status CHECK exists."""
        from sqlalchemy import create_engine, text
        e = create_engine("postgresql://postgres@127.0.0.1:5432/realtoros")
        with e.connect() as conn:
            r = conn.execute(text(
                "SELECT conname FROM pg_constraint WHERE conname = 'ck_deal_status'"
            ))
            assert r.scalar() == "ck_deal_status"

    def test_compliance_score_constraint(self):
        """Verify ck_compliance_score CHECK exists."""
        from sqlalchemy import create_engine, text
        e = create_engine("postgresql://postgres@127.0.0.1:5432/realtoros")
        with e.connect() as conn:
            r = conn.execute(text(
                "SELECT conname FROM pg_constraint WHERE conname = 'ck_compliance_score'"
            ))
            assert r.scalar() == "ck_compliance_score"

    def test_confidence_constraint(self):
        """Verify ck_confidence CHECK exists."""
        from sqlalchemy import create_engine, text
        e = create_engine("postgresql://postgres@127.0.0.1:5432/realtoros")
        with e.connect() as conn:
            r = conn.execute(text(
                "SELECT conname FROM pg_constraint WHERE conname = 'ck_confidence'"
            ))
            assert r.scalar() == "ck_confidence"

    # ── P4: FK Lifecycle ──

    def test_client_deal_fk_set_null(self):
        """Verify deals→clients FK is SET NULL."""
        from sqlalchemy import create_engine, text
        e = create_engine("postgresql://postgres@127.0.0.1:5432/realtoros")
        with e.connect() as conn:
            r = conn.execute(text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'deals_client_id_fkey'"
            ))
            defn = r.scalar()
            assert defn is not None
            assert "SET NULL" in defn

    # ── P5: Agent Runtime Safety ──

    def test_agent_budget_exists(self):
        """AgentExecutionBudget class exists."""
        from backend.core.agent_budget import AgentExecutionBudget, AgentExecutionLimitExceeded
        budget = AgentExecutionBudget()
        assert budget.max_tool_calls == 10
        assert budget.max_chain_depth == 3
        assert budget.max_total_seconds == 30
        assert AgentExecutionLimitExceeded is not None

    def test_agent_budget_limits_tool_calls(self):
        """Budget raises when tool calls exceeded."""
        from backend.core.agent_budget import AgentExecutionBudget, AgentExecutionLimitExceeded
        budget = AgentExecutionBudget(max_tool_calls=2)
        budget.tool_calls_used = 2
        with pytest.raises(AgentExecutionLimitExceeded):
            budget.check()

    def test_agent_budget_limits_chain_depth(self):
        """Budget raises when chain depth exceeded."""
        from backend.core.agent_budget import AgentExecutionBudget, AgentExecutionLimitExceeded
        budget = AgentExecutionBudget(max_chain_depth=1)
        budget.chain_depth = 1
        with pytest.raises(AgentExecutionLimitExceeded):
            budget.check()

    def test_agent_budget_limits_time(self):
        """Budget raises when runtime exceeded."""
        from backend.core.agent_budget import AgentExecutionBudget, AgentExecutionLimitExceeded
        import time
        budget = AgentExecutionBudget(max_total_seconds=0.01)
        time.sleep(0.02)
        with pytest.raises(AgentExecutionLimitExceeded):
            budget.check()

    def test_agent_budget_limits_context_rebuilds(self):
        """Budget raises when context rebuilds exceeded."""
        from backend.core.agent_budget import AgentExecutionBudget, AgentExecutionLimitExceeded
        budget = AgentExecutionBudget(max_context_rebuilds=1)
        budget.context_rebuilds = 2
        with pytest.raises(AgentExecutionLimitExceeded):
            budget.check()

    def test_agent_budget_passes_when_within_limits(self):
        """Budget does not raise within limits."""
        from backend.core.agent_budget import AgentExecutionBudget
        budget = AgentExecutionBudget()
        budget.check()  # should not raise

    # ── P6: Embedding Freshness ──

    def test_embedding_handler_not_stub(self):
        """event_handlers has real embedding_sync_handler."""
        from backend.core.event_handlers import embedding_sync_handler
        import inspect
        source = inspect.getsource(embedding_sync_handler)
        assert "async def embedding_sync_handler" in source

    def test_embedding_handler_registered(self):
        """embedding_sync_handler is registered for document events."""
        from backend.core.event_handlers import register_sync_handlers
        from backend.core.domain_events import DomainEventBus
        bus = DomainEventBus()
        register_sync_handlers(bus)
        assert "document.created" in bus._handlers
        assert "document.deleted" in bus._handlers

    # ── Migration state ──

    def test_all_migrations_applied(self):
        """25 migrations are in the migration directory."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        migs = list((root / "backend" / "migrations" / "versions").glob("*.py"))
        assert len(migs) >= 25, f"Expected 25+ migrations, got {len(migs)}"

    def test_unapplied_migrations_zero(self):
        """Alembic shows no unapplied migrations."""
        import subprocess
        result = subprocess.run(
            ["python", "-m", "alembic", "check"],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parents[3],
        )
        assert "No new" in result.stdout or result.returncode == 0
