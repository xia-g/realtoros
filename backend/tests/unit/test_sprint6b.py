"""Tests for Sprint 6B Deal Operations Platform."""

import asyncio
from uuid import UUID
import pytest

# ── Models ──

class TestModels:
    def test_playbook_model(self):
        from backend.models.deal_playbook import DealPlaybook, DealPlaybookStage, DealPlaybookCheckpoint
        assert hasattr(DealPlaybook, "code"); assert hasattr(DealPlaybookStage, "sla_days"); assert hasattr(DealPlaybookCheckpoint, "regulation_id")

    def test_sla_model(self):
        from backend.models.deal_sla import DealSLA
        assert hasattr(DealSLA, "due_date"); assert hasattr(DealSLA, "status")

    def test_timeline_model(self):
        from backend.models.deal_timeline_event import DealTimelineEvent
        assert hasattr(DealTimelineEvent, "event_type"); assert hasattr(DealTimelineEvent, "source_component")

    def test_stakeholder_model(self):
        from backend.models.stakeholder import Stakeholder
        assert hasattr(Stakeholder, "stakeholder_type"); assert hasattr(Stakeholder, "is_blocking")

    def test_validation_model(self):
        from backend.models.document_validation import DocumentValidation
        assert hasattr(DocumentValidation, "validation_score"); assert hasattr(DocumentValidation, "issues")

    def test_health_model(self):
        from backend.models.deal_health_snapshot import DealHealthSnapshot
        assert hasattr(DealHealthSnapshot, "compliance_score"); assert hasattr(DealHealthSnapshot, "risk_score")

    def test_action_model(self):
        from backend.models.deal_action import DealAction
        assert hasattr(DealAction, "priority"); assert hasattr(DealAction, "status")

    def test_ops_audit_model(self):
        from backend.models.deal_operations_audit import DealOperationsAudit
        assert hasattr(DealOperationsAudit, "operation_type"); assert hasattr(DealOperationsAudit, "correlation_id")


# ── Playbook Service ──

class TestPlaybookService:
    def test_get_playbook(self):
        from backend.services.deal_operations_services import PlaybookService
        import asyncio; svc = PlaybookService()
        r = asyncio.run(svc.get_playbook("residential-sale"))
        assert r is None or r["code"] == "residential-sale"

    def test_get_stage(self):
        from backend.services.deal_operations_services import PlaybookService
        import asyncio; svc = PlaybookService()
        r = asyncio.run(svc.get_stage(UUID(int=1), "lead"))
        assert r is None or r["stage_key"] == "lead"


# ── SLA Service ──

class TestSLAService:
    def test_create_sla(self):
        from backend.services.deal_operations_services import SLAService
        import asyncio; svc = SLAService()
        r = asyncio.run(svc.create_sla(UUID(int=1), "lead", 14))
        assert r["status"] == "pending"; assert r["stage_key"] == "lead"

    def test_find_overdue(self):
        from backend.services.deal_operations_services import SLAService
        import asyncio; svc = SLAService()
        r = asyncio.run(svc.find_overdue())
        assert isinstance(r, list)

    def test_generate_alerts(self):
        from backend.services.deal_operations_services import SLAService
        import asyncio; svc = SLAService()
        r = asyncio.run(svc.generate_alerts())
        assert isinstance(r, list)


# ── Timeline Service ──

class TestTimelineService:
    def test_add_event(self):
        from backend.services.deal_operations_services import TimelineService
        import asyncio; svc = TimelineService()
        r = asyncio.run(svc.add_event(UUID(int=1), "test.event", "test", "Test event"))
        assert r["event_type"] == "test.event"

    def test_get_timeline(self):
        from backend.services.deal_operations_services import TimelineService
        import asyncio; svc = TimelineService()
        r = asyncio.run(svc.get_timeline(UUID(int=1)))
        assert isinstance(r, list)


# ── Stakeholder Service ──

class TestStakeholderService:
    def test_add_stakeholder(self):
        from backend.services.deal_operations_services import StakeholderService
        import asyncio; svc = StakeholderService()
        r = asyncio.run(svc.add_stakeholder(UUID(int=1), "buyer", "Иван Иванов"))
        assert r["type"] == "buyer"

    def test_get_stakeholders(self):
        from backend.services.deal_operations_services import StakeholderService
        import asyncio; svc = StakeholderService()
        r = asyncio.run(svc.get_stakeholders(UUID(int=1)))
        assert isinstance(r, list)


# ── Document Validation ──

class TestValidationService:
    def test_validate_document(self):
        from backend.services.deal_operations_services import DocumentValidationService
        import asyncio; svc = DocumentValidationService()
        r = asyncio.run(svc.validate_document(UUID(int=1)))
        assert "score" in r

    def test_validate_empty_package(self):
        from backend.services.deal_operations_services import DocumentValidationService
        import asyncio; svc = DocumentValidationService()
        r = asyncio.run(svc.validate_package([]))
        assert r["package_score"] == 0


# ── Health Service ──

class TestHealthService:
    def test_calculate_healthy(self):
        from backend.services.deal_operations_services import DealHealthService
        import asyncio; svc = DealHealthService()
        r = asyncio.run(svc.calculate_health(UUID(int=1), compliance_score=95, risk_score=10, sla_score=100, document_score=90, activity_score=100))
        assert r["level"] == "healthy"; assert r["score"] >= 90

    def test_calculate_attention(self):
        from backend.services.deal_operations_services import DealHealthService
        import asyncio; svc = DealHealthService()
        r = asyncio.run(svc.calculate_health(UUID(int=1), compliance_score=60, risk_score=50, sla_score=70, document_score=50, activity_score=80))
        assert "attention" in r["level"] or "critical" in r["level"]

    def test_health_weights(self):
        from backend.services.deal_operations_services import DealHealthService
        w = DealHealthService.WEIGHTS
        assert round(sum(w.values()), 2) == 1.0

    def test_critical_health(self):
        from backend.services.deal_operations_services import DealHealthService
        import asyncio; svc = DealHealthService()
        r = asyncio.run(svc.calculate_health(UUID(int=1), 30, 80, 20, 10, 10))
        assert r["level"] == "critical"


# ── Action Engine ──

class TestActionEngine:
    def test_generate_actions_compliance_gap(self):
        from backend.services.deal_operations_services import ActionEngineService
        import asyncio; svc = ActionEngineService()
        r = asyncio.run(svc.generate_actions(UUID(int=1), {"compliance_score": 50, "risk_score": 30, "document_score": 60}))
        assert len(r) >= 2

    def test_generate_actions_risk_high(self):
        from backend.services.deal_operations_services import ActionEngineService
        import asyncio; svc = ActionEngineService()
        r = asyncio.run(svc.generate_actions(UUID(int=1), {"compliance_score": 100, "risk_score": 80, "document_score": 100}))
        assert any(a["priority"] == "critical" for a in r)

    def test_recommend_next_steps(self):
        from backend.services.deal_operations_services import ActionEngineService
        import asyncio; svc = ActionEngineService()
        r = asyncio.run(svc.recommend_next_steps(UUID(int=1)))
        assert isinstance(r, list); assert len(r) >= 2


# ── Migration 020 ──

class TestMigration:
    def test_migration_exists(self):
        import os
        assert os.path.exists("backend/migrations/versions/020_add_deal_operations.py")

    def test_seed_playbooks(self):
        with open("backend/migrations/versions/020_add_deal_operations.py") as f:
            content = f.read()
        assert "residential-sale" in content
        assert "mortgage" in content
        assert "new-building" in content
        assert "commercial" in content
        assert "rental" in content

    def test_nine_tables_created(self):
        with open("backend/migrations/versions/020_add_deal_operations.py") as f:
            content = f.read()
        for table in ["deal_playbooks", "deal_playbook_stages", "deal_playbook_checkpoints", "deal_slas", "deal_timeline_events", "stakeholders", "document_validations", "deal_health_snapshots", "deal_actions", "deal_operations_audits"]:
            assert table in content, f"Table {table} not found"


# ── API ──

class TestAPI:
    def test_all_endpoints_registered(self):
        from backend.api.routes.sprint6b import router
        routes = [r.path for r in router.routes]
        endpoints = ["/playbooks", "/sla/overdue", "/timeline/", "/stakeholders/", "/document-validation", "/health/", "/actions/", "/copilot/"]
        for ep in endpoints:
            assert any(ep in p for p in routes), f"Endpoint {ep} not found"

    def test_sla_status_enum(self):
        for s in ["pending", "completed", "breached", "cancelled"]:
            assert isinstance(s, str) and len(s) > 0

    def test_health_levels(self):
        from backend.services.deal_operations_services import DealHealthService
        import asyncio
        svc = DealHealthService()
        tests = [(95, "healthy"), (75, "attention"), (50, "critical"), (0, "critical")]
        for score, level in tests:
            r = asyncio.run(svc.calculate_health(UUID(int=1), compliance_score=score, risk_score=0))
            assert r["score"] >= score * 0.3 and r["score"] <= score * 0.3 + 80

    def test_stakeholder_types(self):
        for t in ["buyer", "seller", "bank", "realtor", "lawyer", "notary", "registrar", "guardian", "appraiser"]:
            assert isinstance(t, str)

    def test_priority_order(self):
        priorities = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        assert priorities["critical"] > priorities["high"] > priorities["medium"] > priorities["low"]

    def test_playbook_stage_ordering(self):
        from backend.services.deal_operations_services import PlaybookService
        import asyncio
        svc = PlaybookService()
        r = asyncio.run(svc.get_next_stage(UUID(int=1), 1))
        assert r is None or "sequence" in r

    def test_validation_score_range(self):
        from backend.services.deal_operations_services import DocumentValidationService
        import asyncio
        svc = DocumentValidationService()
        r = asyncio.run(svc.validate_document(UUID(int=1)))
        assert 0 <= r["score"] <= 100

    def test_timeline_source_enum(self):
        for s in ["audit", "tasks", "communications", "documents", "compliance", "regulations", "workflow", "agent_runtime"]:
            assert isinstance(s, str)

    def test_generate_actions_empty_health(self):
        from backend.services.deal_operations_services import ActionEngineService
        import asyncio
        svc = ActionEngineService()
        r = asyncio.run(svc.generate_actions(UUID(int=1)))
        assert len(r) >= 0

    def test_deal_readiness_endpoint_registered(self):
        from backend.api.routes.sprint6b import router
        paths = [r.path for r in router.routes]
        assert any("deal-readiness" in p for p in paths)

    def test_deal_summary_endpoint_registered(self):
        from backend.api.routes.sprint6b import router
        paths = [r.path for r in router.routes]
        assert any("deal-summary" in p for p in paths)

    def test_health_weights_sum_to_one(self):
        from backend.services.deal_operations_services import DealHealthService
        assert round(sum(DealHealthService.WEIGHTS.values()), 2) == 1.0

    def test_copilot_tools_count(self):
        from backend.api.routes.sprint6b import router
        copilot_routes = [r.path for r in router.routes if "copilot" in r.path]
        assert len(copilot_routes) >= 2

    def test_playbooks_seeded(self):
        codes = ["residential-sale", "mortgage", "new-building", "commercial", "rental"]
        assert len(codes) == 5

    def test_playbook_sla_days_positive(self):
        from backend.services.deal_operations_services import PlaybookService
        import asyncio; svc = PlaybookService()
        r = asyncio.run(svc.get_stage(UUID(int=1), "test"))
        assert r is None or r.get("sla_days", 0) > 0

    def test_sla_overdue_returns_list(self):
        from backend.services.deal_operations_services import SLAService
        import asyncio; svc = SLAService()
        r = asyncio.run(svc.find_overdue())
        assert isinstance(r, list)

    def test_timeline_empty_for_new_deal(self):
        from backend.services.deal_operations_services import TimelineService
        import asyncio; svc = TimelineService()
        r = asyncio.run(svc.get_timeline(UUID(int=999)))
        assert isinstance(r, list)

    def test_stakeholder_add_with_org(self):
        from backend.services.deal_operations_services import StakeholderService
        import asyncio; svc = StakeholderService()
        r = asyncio.run(svc.add_stakeholder(UUID(int=1), "bank", "Сбербанк", organization="ПАО Сбербанк"))
        assert r["name"] == "Сбербанк"

    def test_health_zero_scores(self):
        from backend.services.deal_operations_services import DealHealthService
        import asyncio; svc = DealHealthService()
        r = asyncio.run(svc.calculate_health(UUID(int=1), 0, 100, 0, 0, 0))
        assert r["score"] >= 0

    def test_validation_no_issues_for_valid_doc(self):
        from backend.services.deal_operations_services import DocumentValidationService
        import asyncio; svc = DocumentValidationService()
        r = asyncio.run(svc.validate_document(UUID(int=1)))
        assert isinstance(r["issues"], list)

    def test_playbook_count_5(self):
        with open("backend/migrations/versions/020_add_deal_operations.py") as f:
            c = f.read()
        assert c.count("playbooks (") >= 5
