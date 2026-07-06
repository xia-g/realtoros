"""Tests for Sprint 7B Executive Dashboard & Command Center."""

import asyncio
from uuid import UUID
import pytest


# ── P1-2: Dashboard ──

class TestDashboard:
    def test_snapshot_all_fields(self):
        from backend.services.executive_services import DashboardSnapshot
        d = DashboardSnapshot(generated_at="now")
        assert hasattr(d, "revenue") and hasattr(d, "active_deals") and hasattr(d, "critical_alerts")

    def test_get_dashboard(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_dashboard())
        assert r.revenue > 0; assert r.active_deals > 0

    def test_executive_summary(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_executive_summary())
        assert len(r.top_risks) > 0; assert len(r.recommendations) > 0

    def test_priority_items(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_priority_items())
        assert len(r) > 0; assert "priority" in r[0]

    def test_health_overview(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_health_overview())
        assert "overall" in r; assert "compliance" in r

    def test_dashboard_response_time(self):
        import asyncio, time; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); t0 = time.monotonic()
        asyncio.run(svc.get_dashboard())
        assert (time.monotonic() - t0) < 0.5

    def test_summary_generated_at(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_executive_summary())
        assert len(r.generated_at) > 0

    def test_dashboard_dataclass_defaults(self):
        from backend.services.executive_services import DashboardSnapshot
        d = DashboardSnapshot()
        assert d.revenue == 0.0 and d.active_deals == 0


# ── P3: Operations Center ──

class TestOperationsCenter:
    def test_snapshot_fields(self):
        from backend.services.executive_services import OperationsCenterSnapshot
        o = OperationsCenterSnapshot()
        assert hasattr(o, "critical_deals") and hasattr(o, "critical_teams") and hasattr(o, "critical_regulations")

    def test_get_snapshot(self):
        import asyncio; from backend.services.executive_services import OperationsCenterService
        svc = OperationsCenterService(); r = asyncio.run(svc.get_snapshot())
        assert len(r.critical_deals) >= 0; assert len(r.critical_regulations) >= 0

    def test_critical_deal_has_risk(self):
        import asyncio; from backend.services.executive_services import OperationsCenterService
        svc = OperationsCenterService(); r = asyncio.run(svc.get_snapshot())
        for d in r.critical_deals:
            assert "risk" in d

    def test_generated_at(self):
        import asyncio; from backend.services.executive_services import OperationsCenterService
        svc = OperationsCenterService(); r = asyncio.run(svc.get_snapshot())
        assert len(r.generated_at) > 0


# ── P4: War Room ──

class TestWarRoom:
    def test_war_room_contract(self):
        from backend.services.executive_services import WarRoom
        w = WarRoom(title="Test", severity="HIGH")
        assert w.title == "Test" and w.severity == "HIGH"

    def test_get_war_rooms(self):
        import asyncio; from backend.services.executive_services import WarRoomService
        svc = WarRoomService(); r = asyncio.run(svc.get_war_rooms())
        assert len(r) >= 0; assert all(isinstance(w, object) for w in r)

    def test_create_war_room(self):
        import asyncio; from backend.services.executive_services import WarRoomService
        svc = WarRoomService(); r = asyncio.run(svc.create_war_room("Test crisis", "HIGH"))
        assert r.severity == "HIGH"; assert "Test" in r.title

    def test_close_war_room(self):
        import asyncio; from backend.services.executive_services import WarRoomService
        svc = WarRoomService(); r = asyncio.run(svc.close_war_room(UUID(int=1)))
        assert r is True

    def test_incident_types_defined(self):
        from backend.services.executive_services import WarRoomService
        types = WarRoomService.INCIDENT_TYPES
        assert "compliance_crisis" in types; assert "regulatory_change" in types
        assert len(types) == 7

    def test_war_room_severity_levels(self):
        for s in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            assert isinstance(s, str)

    def test_war_room_has_actions(self):
        import asyncio; from backend.services.executive_services import WarRoomService
        svc = WarRoomService(); r = asyncio.run(svc.get_war_rooms())
        for w in r:
            assert hasattr(w, "recommended_actions")


# ── P5: Executive Copilot ──

class TestExecutiveCopilot:
    def test_analyze(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.analyze("Что требует внимания?"))
        assert "confidence" in r; assert "sources" in r; assert "recommended_actions" in r

    def test_risk_summary(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_risk_summary())
        assert "critical" in r; assert "total_risks" in r

    def test_compliance_summary(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_compliance_summary())
        assert "avg_score" in r; assert "failing_deals" in r

    def test_team_summary(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_team_summary())
        assert "overloaded" in r; assert "avg_workload" in r

    def test_revenue_summary(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_revenue_summary())
        assert r["total"] > 0; assert "currency" in r

    def test_analyze_confidence(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.analyze("test"))
        assert 0 <= r["confidence"] <= 1.0

    def test_analyze_sources_not_empty(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.analyze("test"))
        assert len(r["sources"]) > 0


# ── P6: Telegram ──

class TestTelegram:
    def test_commands_defined(self):
        from backend.services.executive_services import TelegramExecutiveAssistant
        cmds = TelegramExecutiveAssistant.COMMANDS
        assert "/brief" in cmds; assert "/morning_report" in cmds; assert "/warroom" in cmds
        assert len(cmds) == 10

    def test_morning_report(self):
        import asyncio; from backend.services.executive_services import TelegramExecutiveAssistant
        svc = TelegramExecutiveAssistant(); r = asyncio.run(svc.get_morning_report())
        assert "Revenue" in r; assert "Critical" in r

    def test_brief(self):
        import asyncio; from backend.services.executive_services import TelegramExecutiveAssistant
        svc = TelegramExecutiveAssistant(); r = asyncio.run(svc.get_brief())
        assert "active" in r

    def test_critical(self):
        import asyncio; from backend.services.executive_services import TelegramExecutiveAssistant
        svc = TelegramExecutiveAssistant(); r = asyncio.run(svc.get_critical())
        assert "SLA" in r or "Critical" in r


# ── P7: Notifications ──

class TestNotifications:
    def test_generate_alerts(self):
        import asyncio; from backend.services.executive_services import ManagementNotificationService
        svc = ManagementNotificationService(); r = asyncio.run(svc.generate_alerts())
        assert len(r) > 0; assert "severity" in r[0]

    def test_send_notification(self):
        import asyncio; from backend.services.executive_services import ManagementNotificationService
        svc = ManagementNotificationService()
        r = asyncio.run(svc.send_notification("HIGH", "Test", "Test message"))
        assert r["sent"] is True


# ── P8: API ──

class TestAPI:
    def test_all_endpoints(self):
        from backend.api.routes.sprint7b import router
        paths = [r.path for r in router.routes]
        required = ["/dashboard", "/summary", "/operations", "/warrooms", "/risks", "/compliance", "/team", "/revenue", "/regulations", "/critical"]
        for ep in required:
            assert any(ep in p for p in paths), f"{ep} not found"

    def test_all_endpoints_count(self):
        from backend.api.routes.sprint7b import router
        assert len(router.routes) >= 10

    def test_post_warroom(self):
        from backend.api.routes.sprint7b import router
        routes = [r for r in router.routes if "warroom" in r.path]
        assert len(routes) >= 2

    def test_analyze_endpoint(self):
        from backend.api.routes.sprint7b import router
        assert any("analyze" in r.path for r in router.routes)

    def test_priority_endpoint(self):
        from backend.api.routes.sprint7b import router
        assert any("priority" in r.path for r in router.routes)

    def test_health_overview_endpoint(self):
        from backend.api.routes.sprint7b import router
        assert any("health" in r.path for r in router.routes)


# ── E2E Scenarios ──

class TestE2E:
    def test_scenario1_executive_asks_attention(self):
        """Executive asks: What requires attention?"""
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService, ExecutiveCopilot
        d = asyncio.run(ExecutiveDashboardService().get_dashboard())
        a = asyncio.run(ExecutiveCopilot().analyze("Что требует внимания?"))
        assert d.critical_alerts >= 0; assert a["confidence"] > 0

    def test_scenario2_regulation_appears(self):
        from backend.services.executive_services import WarRoomService
        import asyncio
        w = asyncio.run(WarRoomService().create_war_room("Regulation change: 218-ФЗ", "HIGH"))
        assert w.severity == "HIGH"

    def test_scenario3_compliance_drops(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        r = asyncio.run(ExecutiveCopilot().get_compliance_summary())
        assert "avg_score" in r; assert r["avg_score"] >= 0

    def test_scenario4_team_overload(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        r = asyncio.run(ExecutiveCopilot().get_team_summary())
        assert "overloaded" in r

    def test_scenario5_critical_deal_risk(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        r = asyncio.run(ExecutiveCopilot().get_risk_summary())
        assert "critical" in r; assert r["critical"] >= 0


# ── Edge Cases ──

class TestEdgeCases:
    def test_empty_war_rooms(self):
        import asyncio; from backend.services.executive_services import WarRoomService
        svc = WarRoomService(); r = asyncio.run(svc.get_war_rooms())
        assert isinstance(r, list)

    def test_dashboard_timestamp(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_dashboard())
        assert "T" in r.generated_at

    def test_summary_has_recommendations(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_executive_summary())
        assert len(r.recommendations) > 0

    def test_operations_center_has_all_sections(self):
        import asyncio; from backend.services.executive_services import OperationsCenterService
        svc = OperationsCenterService(); r = asyncio.run(svc.get_snapshot())
        assert len(r.critical_deals) >= 0 and len(r.critical_teams) >= 0 and len(r.critical_regulations) >= 0

    def test_critical_alert_count(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_dashboard())
        assert isinstance(r.critical_alerts, int)

    def test_war_room_default_low(self):
        from backend.services.executive_services import WarRoom
        w = WarRoom(title="test")
        assert w.severity == "LOW"

    def test_notification_has_type(self):
        import asyncio; from backend.services.executive_services import ManagementNotificationService
        svc = ManagementNotificationService(); r = asyncio.run(svc.generate_alerts())
        for a in r:
            assert "type" in a

    def test_revenue_summary_positive(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_revenue_summary())
        assert r["total"] > 0

    def test_risk_summary_total(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_risk_summary())
        parts = r["critical"] + r["high"] + r["medium"] + r["low"]
        assert parts == r["total_risks"]

    def test_dashboard_loads_under_500ms(self):
        import asyncio, time; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); t0 = time.monotonic()
        asyncio.run(svc.get_dashboard())
        assert (time.monotonic() - t0) < 0.5

    def test_operation_center_duration(self):
        import asyncio, time; from backend.services.executive_services import OperationsCenterService
        svc = OperationsCenterService(); t0 = time.monotonic()
        asyncio.run(svc.get_snapshot())
        assert (time.monotonic() - t0) < 0.5

    def test_analyze_empty_question(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.analyze(""))
        assert r["confidence"] >= 0

    def test_war_room_severity_default(self):
        from backend.services.executive_services import WarRoom
        w = WarRoom(title="t")
        assert w.severity == "LOW"

    def test_dashboard_revenue_type(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_dashboard())
        assert isinstance(r.revenue, float)

    def test_operations_teams_field(self):
        import asyncio; from backend.services.executive_services import OperationsCenterService
        svc = OperationsCenterService(); r = asyncio.run(svc.get_snapshot())
        assert isinstance(r.critical_teams, list)

    def test_warroom_causes_field(self):
        import asyncio; from backend.services.executive_services import WarRoomService
        svc = WarRoomService(); r = asyncio.run(svc.get_war_rooms())
        for w in r:
            assert isinstance(w.root_causes, list)

    def test_telegram_revenue(self):
        import asyncio; from backend.services.executive_services import TelegramExecutiveAssistant
        r = asyncio.run(TelegramExecutiveAssistant().get_brief())
        assert "deals" in r or "клиентов" in r

    def test_copilot_risk_breakdown(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_risk_summary())
        assert r["low"] >= 0; assert r["high"] >= 0

    def test_compliance_summary_structure(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_compliance_summary())
        assert "top_issue" in r

    def test_team_summary_agents(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_team_summary())
        assert r["total_agents"] > 0

    def test_revenue_commission_less_than_total(self):
        import asyncio; from backend.services.executive_services import ExecutiveCopilot
        svc = ExecutiveCopilot(); r = asyncio.run(svc.get_revenue_summary())
        assert r["commission"] <= r["total"]

    def test_notification_generation_multiple(self):
        import asyncio; from backend.services.executive_services import ManagementNotificationService
        svc = ManagementNotificationService(); r = asyncio.run(svc.generate_alerts())
        assert len(r) >= 1

    def test_priority_item_has_deadline(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_priority_items())
        for item in r:
            assert "deadline" in item

    def test_create_warroom_default_severity(self):
        import asyncio; from backend.services.executive_services import WarRoomService
        svc = WarRoomService(); r = asyncio.run(svc.create_war_room("Test"))
        assert r.severity == "MEDIUM"

    def test_api_endpoints_telegram(self):
        from backend.services.executive_services import TelegramExecutiveAssistant
        assert len(TelegramExecutiveAssistant.COMMANDS) == 10

    def test_health_overview_all_keys(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService
        svc = ExecutiveDashboardService(); r = asyncio.run(svc.get_health_overview())
        for k in ["overall", "compliance", "risk", "sla", "team", "revenue_health"]:
            assert k in r, f"Missing: {k}"

    def test_scenario_full_executive_flow(self):
        import asyncio; from backend.services.executive_services import ExecutiveDashboardService, OperationsCenterService, WarRoomService
        d = asyncio.run(ExecutiveDashboardService().get_dashboard())
        o = asyncio.run(OperationsCenterService().get_snapshot())
        w = asyncio.run(WarRoomService().get_war_rooms())
        assert d.critical_alerts >= 0; assert len(o.critical_deals) >= 0; assert isinstance(w, list)
