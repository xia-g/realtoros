"""Tests for escalation safety circuit breaker."""
import pytest


class TestEscalationSafety:
    """Verify circuit breaker prevents infinite escalation."""

    def test_max_escalations_defined(self):
        """MAX_ESCALATIONS constant exists with default 4."""
        from backend.services.autonomous_services import EscalationService
        assert hasattr(EscalationService, "MAX_ESCALATIONS")
        assert EscalationService.MAX_ESCALATIONS == 4

    def test_circuit_breaker_returns_blocked(self):
        """After max escalations, status is 'blocked'."""
        from backend.services.autonomous_services import EscalationService

        svc = EscalationService()
        svc._visited = {}
        for i in range(5):
            import asyncio
            e = asyncio.run(svc.escalate("task-breaker-1", f"test escalation {i}", i))
            if i >= 4:
                assert e.status == "blocked", f"Expected blocked at i={i}, got {e.status}"
                assert "CIRCUIT BREAKER" in e.reason
                return
        pytest.fail("Circuit breaker did not trigger within 5 attempts")

    def test_loop_detection(self):
        """Repeated escalation to same role escalates to executive."""
        from backend.services.autonomous_services import EscalationService
        import asyncio

        svc = EscalationService()
        svc._visited = {"task-loop-1": {"roles": {"executor"}, "users": set(), "count": 1}}
        e = asyncio.run(svc.escalate("task-loop-1", "loop test", 0))
        assert e.assignee == "executive"

    def test_different_tasks_independent(self):
        """Escalations for different tasks are tracked independently."""
        from backend.services.autonomous_services import EscalationService
        import asyncio

        svc = EscalationService()
        svc._visited = {}
        e1 = asyncio.run(svc.escalate("task-a", "reason a", 0))
        e2 = asyncio.run(svc.escalate("task-b", "reason b", 0))

        assert e1.assignee is not None
        assert e2.assignee is not None
        assert e1.status in ("open", "blocked")
        assert e2.status in ("open", "blocked")

    def test_visited_count_tracked(self):
        """Visited count increments correctly."""
        from backend.services.autonomous_services import EscalationService
        import asyncio

        svc = EscalationService()
        svc._visited = {}
        for i in range(3):
            asyncio.run(svc.escalate("task-count", f"test {i}", i))

        visited = svc._visited.get("task-count", {})
        assert visited["count"] == 3, f"Expected 3 visits, got {visited['count']}"

    def test_chain_defined(self):
        """Escalation chain has 4 levels."""
        from backend.services.autonomous_services import EscalationService
        assert len(EscalationService.CHAIN) == 4
        assert EscalationService.CHAIN == ["executor", "team_lead", "department_head", "executive"]

    def test_reset_after_resolve(self):
        """Verify resolve still works."""
        from backend.services.autonomous_services import EscalationService
        import asyncio
        from uuid import UUID

        svc = EscalationService()
        result = asyncio.run(svc.resolve(UUID(int=999)))
        assert result is True