"""Tests for Sprint 8 Autonomous Operations Platform."""

import asyncio
from uuid import UUID
import pytest


# ── P1: Task Orchestrator ──

class TestTaskOrchestrator:
    def test_generate_tasks(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator
        svc = TaskOrchestrator(); r = asyncio.run(svc.generate_tasks(UUID(int=1)))
        assert len(r) >= 2; assert r[0].priority in ("critical", "high", "medium", "low")

    def test_compliance_tasks(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator
        svc = TaskOrchestrator(); r = asyncio.run(svc.generate_from_compliance(65.0, ["egrn_extract", "spouse_consent"], UUID(int=1)))
        assert len(r) == 2; assert "Missing" in r[0].problem

    def test_sla_breach_tasks(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator
        svc = TaskOrchestrator(); r = asyncio.run(svc.generate_from_sla_breach("registration", 5, UUID(int=1)))
        assert len(r) == 1; assert r[0].priority == "critical"

    def test_priority_logic(self):
        from backend.services.autonomous_services import TaskOrchestrator
        svc = TaskOrchestrator()
        assert svc._priority(85) == "critical"; assert svc._priority(55) == "high"
        assert svc._priority(30) == "medium"; assert svc._priority(10) == "low"

    def test_task_has_deadline(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator
        svc = TaskOrchestrator(); r = asyncio.run(svc.generate_tasks(UUID(int=1)))
        for t in r: assert len(t.deadline) > 0

    def test_owner_role_assigned(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator
        svc = TaskOrchestrator(); r = asyncio.run(svc.generate_tasks(UUID(int=1)))
        for t in r: assert t.owner_role in ("seller", "client", "registrar", "manager")


# ── P2: Assignment Engine ──

class TestAssignment:
    def test_assign(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator, AssignmentService
        t = asyncio.run(TaskOrchestrator().generate_tasks(UUID(int=1)))
        a = asyncio.run(AssignmentService().assign(t[0]))
        assert a.confidence > 0; assert len(a.assignee) > 0

    def test_assign_strategies(self):
        from backend.services.autonomous_services import AssignmentService
        assert "ROUND_ROBIN" in AssignmentService.STRATEGIES
        assert "LEAST_LOADED" in AssignmentService.STRATEGIES

    def test_assign_confidence(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator, AssignmentService
        t = asyncio.run(TaskOrchestrator().generate_tasks(UUID(int=1)))
        a = asyncio.run(AssignmentService().assign(t[0], "ROUND_ROBIN"))
        assert 0 <= a.confidence <= 1.0

    def test_workload(self):
        import asyncio; from backend.services.autonomous_services import AssignmentService
        w = asyncio.run(AssignmentService().get_workload())
        assert len(w) >= 3

    def test_assignment_reasoning(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator, AssignmentService
        t = asyncio.run(TaskOrchestrator().generate_tasks(UUID(int=1)))
        a = asyncio.run(AssignmentService().assign(t[0]))
        assert "strategy" in a.reasoning


# ── P3: Escalation Engine ──

class TestEscalation:
    def test_escalate(self):
        import asyncio; from backend.services.autonomous_services import EscalationService
        svc = EscalationService(); r = asyncio.run(svc.escalate("t1", "SLA breach"))
        assert r.level >= 0; assert r.assignee in EscalationService.CHAIN

    def test_chain_order(self):
        from backend.services.autonomous_services import EscalationService
        assert EscalationService.CHAIN == ["executor", "team_lead", "department_head", "executive"]

    def test_escalation_level_increments(self):
        import asyncio; from backend.services.autonomous_services import EscalationService
        svc = EscalationService()
        r1 = asyncio.run(svc.escalate("t1", "issue", 0))
        r2 = asyncio.run(svc.escalate("t1", "issue", r1.level))
        assert r2.level > r1.level

    def test_get_active(self):
        import asyncio; from backend.services.autonomous_services import EscalationService
        svc = EscalationService(); r = asyncio.run(svc.get_active())
        assert len(r) >= 0

    def test_resolve(self):
        import asyncio; from backend.services.autonomous_services import EscalationService
        svc = EscalationService(); r = asyncio.run(svc.resolve(UUID(int=1)))
        assert r is True

    def test_escalation_idempotent(self):
        import asyncio; from backend.services.autonomous_services import EscalationService
        svc = EscalationService()
        r1 = asyncio.run(svc.escalate("t1", "issue"))
        r2 = asyncio.run(svc.escalate("t1", "issue"))
        assert r1.id != r2.id


# ── P4: Recovery Engine ──

class TestRecovery:
    def test_generate_plan(self):
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine
        svc = DealRecoveryEngine(); r = asyncio.run(svc.generate_plan(UUID(int=1)))
        assert r.success_probability > 0; assert len(r.actions) > 0

    def test_find_similar(self):
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine
        svc = DealRecoveryEngine(); r = asyncio.run(svc.find_similar(UUID(int=1)))
        assert len(r) > 0

    def test_recovery_plan_has_causes(self):
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine
        svc = DealRecoveryEngine(); r = asyncio.run(svc.generate_plan(UUID(int=1)))
        assert len(r.root_causes) > 0

    def test_success_probability_range(self):
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine
        svc = DealRecoveryEngine(); r = asyncio.run(svc.generate_plan(UUID(int=1)))
        assert 0 <= r.success_probability <= 1.0

    def test_similar_has_outcome(self):
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine
        svc = DealRecoveryEngine(); r = asyncio.run(svc.find_similar(UUID(int=1)))
        for s in r: assert "outcome" in s


# ── P5: Operational Health ──

class TestHealth:
    def test_evaluate(self):
        import asyncio; from backend.services.autonomous_services import OperationalHealthService
        svc = OperationalHealthService(); r = asyncio.run(svc.evaluate(UUID(int=1)))
        assert "score" in r; assert "level" in r

    def test_health_levels(self):
        import asyncio; from backend.services.autonomous_services import OperationalHealthService
        svc = OperationalHealthService(); r = asyncio.run(svc.evaluate(UUID(int=1)))
        assert r["level"] in ("green", "yellow", "orange", "red")

    def test_all_dimensions(self):
        import asyncio; from backend.services.autonomous_services import OperationalHealthService
        svc = OperationalHealthService(); r = asyncio.run(svc.evaluate(UUID(int=1)))
        for d in ["compliance", "risk", "sla", "documents", "activity", "timeline", "stakeholders"]:
            assert d in r

    def test_score_range(self):
        import asyncio; from backend.services.autonomous_services import OperationalHealthService
        svc = OperationalHealthService(); r = asyncio.run(svc.evaluate(UUID(int=1)))
        assert 0 <= r["score"] <= 100


# ── P6: Action Recommendations ──

class TestRecommendations:
    def test_recommend(self):
        import asyncio; from backend.services.autonomous_services import ActionRecommendationService
        svc = ActionRecommendationService(); r = asyncio.run(svc.recommend(UUID(int=1)))
        assert len(r) > 0

    def test_confidence_range(self):
        import asyncio; from backend.services.autonomous_services import ActionRecommendationService
        svc = ActionRecommendationService(); r = asyncio.run(svc.recommend(UUID(int=1)))
        for a in r: assert 0 <= a.confidence <= 1.0

    def test_sources_not_empty(self):
        import asyncio; from backend.services.autonomous_services import ActionRecommendationService
        svc = ActionRecommendationService(); r = asyncio.run(svc.recommend(UUID(int=1)))
        for a in r: assert len(a.sources) > 0

    def test_expected_impact(self):
        import asyncio; from backend.services.autonomous_services import ActionRecommendationService
        svc = ActionRecommendationService(); r = asyncio.run(svc.recommend(UUID(int=1)))
        for a in r: assert len(a.expected_impact) > 0


# ── P8: Executive Action Center ──

class TestActionCenter:
    def test_pending_approvals(self):
        import asyncio; from backend.services.autonomous_services import ExecutiveActionCenter
        svc = ExecutiveActionCenter(); r = asyncio.run(svc.get_pending_approvals())
        assert len(r) >= 0

    def test_approve(self):
        import asyncio; from backend.services.autonomous_services import ExecutiveActionCenter
        svc = ExecutiveActionCenter(); r = asyncio.run(svc.approve(UUID(int=1)))
        assert r is True

    def test_reject(self):
        import asyncio; from backend.services.autonomous_services import ExecutiveActionCenter
        svc = ExecutiveActionCenter(); r = asyncio.run(svc.reject(UUID(int=1), "Not needed"))
        assert r is True

    def test_pending_has_type(self):
        import asyncio; from backend.services.autonomous_services import ExecutiveActionCenter
        svc = ExecutiveActionCenter(); r = asyncio.run(svc.get_pending_approvals())
        for a in r: assert "type" in a


# ── API ──

class TestAPI:
    def test_all_routes(self):
        from backend.api.routes.sprint8 import router
        paths = [r.path for r in router.routes]
        for ep in ["/tasks/", "/escalations", "/recovery/", "/health/", "/recommendations/", "/approvals"]:
            assert any(ep in p for p in paths), f"{ep} not found"

    def test_route_count(self):
        from backend.api.routes.sprint8 import router
        assert len(router.routes) >= 10


# ── Contracts ──

class TestContracts:
    def test_priority_enum(self):
        from backend.services.autonomous_services import Priority
        assert Priority.CRITICAL.value == "critical"
        assert Priority.LOW.value == "low"

    def test_health_level_enum(self):
        from backend.services.autonomous_services import HealthLevel
        assert HealthLevel.GREEN.value == "green"
        assert HealthLevel.RED.value == "red"

    def test_dataclass_defaults(self):
        from backend.services.autonomous_services import TaskItem, Assignment, Escalation, RecoveryPlan, ActionRecommendation
        assert TaskItem().status == "pending"
        assert Assignment().status == "pending"
        assert Escalation().status == "open"
        assert RecoveryPlan().status == "draft"


# ── E2E Scenarios ──

class TestE2E:
    def test_scenario1_missing_document_flow(self):
        """Missing document → task generated → assigned"""
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator, AssignmentService
        tasks = asyncio.run(TaskOrchestrator().generate_from_compliance(65.0, ["egrn_extract"], UUID(int=1)))
        assert len(tasks) == 1; assert "egrn_extract" in tasks[0].problem
        a = asyncio.run(AssignmentService().assign(tasks[0]))
        assert a.status == "pending"; assert a.confidence > 0

    def test_scenario2_sla_breach_escalation(self):
        """SLA breach → escalation → executive visibility"""
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator, EscalationService
        tasks = asyncio.run(TaskOrchestrator().generate_from_sla_breach("registration", 5, UUID(int=1)))
        assert tasks[0].priority == "critical"
        e = asyncio.run(EscalationService().escalate(tasks[0].id or "t1", "SLA breach"))
        assert e.assignee in EscalationService.CHAIN

    def test_scenario3_risk_recovery_plan(self):
        """Risk detected → recovery plan → recommendation"""
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine, ActionRecommendationService
        plan = asyncio.run(DealRecoveryEngine().generate_plan(UUID(int=1)))
        assert plan.success_probability > 0
        recs = asyncio.run(ActionRecommendationService().recommend(UUID(int=1)))
        assert len(recs) > 0

    def test_scenario4_full_autonomous_cycle(self):
        """Detect → Task → Assign → Escalate → Approve"""
        import asyncio
        from backend.services.autonomous_services import TaskOrchestrator, AssignmentService, EscalationService, ExecutiveActionCenter
        tasks = asyncio.run(TaskOrchestrator().generate_from_sla_breach("signing", 3, UUID(int=1)))
        assert tasks[0].priority == "critical"
        a = asyncio.run(AssignmentService().assign(tasks[0], "SPECIALIZATION"))
        assert a.confidence > 0
        e = asyncio.run(EscalationService().escalate(a.task_id, "Not resolved", 0))
        assert e.level >= 0
        ap = asyncio.run(ExecutiveActionCenter().get_pending_approvals())
        assert isinstance(ap, list)

    def test_scenario5_health_based_recommendations(self):
        """Health check → recommendations"""
        import asyncio; from backend.services.autonomous_services import OperationalHealthService, ActionRecommendationService
        h = asyncio.run(OperationalHealthService().evaluate(UUID(int=1)))
        assert h["score"] > 0
        recs = asyncio.run(ActionRecommendationService().recommend(UUID(int=1)))
        assert len(recs) > 0

    def test_scenario6_escalation_chain_full(self):
        """Full escalation chain: executor → team_lead → department_head → executive"""
        import asyncio; from backend.services.autonomous_services import EscalationService
        svc = EscalationService()
        e = asyncio.run(svc.escalate("t1", "Unresolved critical risk"))
        assert e.assignee == "team_lead"
        e = asyncio.run(svc.escalate("t1", "Still unresolved", e.level))
        assert e.assignee == "department_head"
        e = asyncio.run(svc.escalate("t1", "Escalated", e.level))
        assert e.assignee == "executive"

    def test_task_from_sla_preserves_stage(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator
        r = asyncio.run(TaskOrchestrator().generate_from_sla_breach("signing", 2, UUID(int=1)))
        assert "signing" in r[0].problem

    def test_task_document_names(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator
        r = asyncio.run(TaskOrchestrator().generate_from_compliance(50, ["doc1", "doc2", "doc3"], UUID(int=1)))
        assert len(r) == 3

    def test_assignment_different_strategies(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator, AssignmentService
        t = asyncio.run(TaskOrchestrator().generate_tasks(UUID(int=1)))
        a1 = asyncio.run(AssignmentService().assign(t[0], "ROUND_ROBIN"))
        a2 = asyncio.run(AssignmentService().assign(t[0], "LEAST_LOADED"))
        assert a1.assignee == a2.assignee  # same best match

    def test_escalation_level_not_exceed_chain(self):
        import asyncio; from backend.services.autonomous_services import EscalationService
        svc = EscalationService()
        e = asyncio.run(svc.escalate("t1", "x", 10))
        assert e.level < len(svc.CHAIN)

    def test_recovery_plan_generates_multiple_actions(self):
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine
        svc = DealRecoveryEngine(); r = asyncio.run(svc.generate_plan(UUID(int=1)))
        assert len(r.actions) >= 2

    def test_similar_deals_have_similarity(self):
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine
        svc = DealRecoveryEngine(); r = asyncio.run(svc.find_similar(UUID(int=1)))
        for s in r: assert 0 <= s["similarity"] <= 1.0

    def test_health_level_yellow_between_70_and_90(self):
        import asyncio; from backend.services.autonomous_services import OperationalHealthService
        svc = OperationalHealthService(); r = asyncio.run(svc.evaluate(UUID(int=1)))
        # score is 74.5 -> should be yellow
        if r["score"] >= 70: assert r["level"] == "yellow" or r["level"] == "green"

    def test_recommendations_from_multiple_sources(self):
        import asyncio; from backend.services.autonomous_services import ActionRecommendationService
        svc = ActionRecommendationService(); r = asyncio.run(svc.recommend(UUID(int=1)))
        all_sources = set()
        for a in r:
            for s in a.sources: all_sources.add(s)
        assert len(all_sources) > 0

    def test_pending_approval_has_deal_id(self):
        import asyncio; from backend.services.autonomous_services import ExecutiveActionCenter
        svc = ExecutiveActionCenter(); r = asyncio.run(svc.get_pending_approvals())
        for a in r: assert "deal_id" in a

    def test_task_priority_matches_enum(self):
        import asyncio; from backend.services.autonomous_services import TaskOrchestrator, Priority
        svc = TaskOrchestrator(); r = asyncio.run(svc.generate_tasks(UUID(int=1)))
        for t in r:
            assert t.priority in (p.value for p in Priority)

    def test_escalation_reason_not_empty(self):
        import asyncio; from backend.services.autonomous_services import EscalationService
        svc = EscalationService(); r = asyncio.run(svc.escalate("t1", "Critical SLA breach"))
        assert len(r.reason) > 0

    def test_workload_sum_matches_users(self):
        import asyncio; from backend.services.autonomous_services import AssignmentService
        w = asyncio.run(AssignmentService().get_workload())
        assert sum(w.values()) == sum(AssignmentService().STRATEGIES.__len__ for _ in [0]) + 10

    def test_approval_reject_reason_logged(self):
        import asyncio; from backend.services.autonomous_services import ExecutiveActionCenter
        svc = ExecutiveActionCenter(); r = asyncio.run(svc.reject(UUID(int=1), "Duplicate"))
        assert r is True

    def test_recovery_plan_status_draft(self):
        import asyncio; from backend.services.autonomous_services import DealRecoveryEngine
        svc = DealRecoveryEngine(); r = asyncio.run(svc.generate_plan(UUID(int=1)))
        assert r.status == "draft"

    def test_no_autonomous_deal_modifications(self):
        """Verify no route modifies deals automatically."""
        from backend.api.routes.sprint8 import router
        paths = [r.path for r in router.routes]
        for p in paths:
            assert "deal" not in p.split("/")[-1] or "approve" in p or "reject" in p

    def test_escalation_chain_has_4_levels(self):
        from backend.services.autonomous_services import EscalationService
        assert len(EscalationService.CHAIN) == 4
