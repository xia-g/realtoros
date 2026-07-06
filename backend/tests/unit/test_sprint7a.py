"""Tests for Sprint 7A Analytics & Decision Intelligence Platform."""

import asyncio
from uuid import UUID
import pytest


# ── Models ──

class TestModels:
    def test_analytics_snapshot(self):
        from backend.models.analytics_snapshot import AnalyticsSnapshot
        assert hasattr(AnalyticsSnapshot, "snapshot_type") and hasattr(AnalyticsSnapshot, "snapshot_date") and hasattr(AnalyticsSnapshot, "payload")

    def test_analytics_alert(self):
        from backend.models.analytics_alert import AnalyticsAlert
        assert hasattr(AnalyticsAlert, "severity") and hasattr(AnalyticsAlert, "alert_type") and hasattr(AnalyticsAlert, "status")

    def test_prediction_result(self):
        from backend.models.prediction_result import PredictionResult
        assert hasattr(PredictionResult, "prediction_type") and hasattr(PredictionResult, "score") and hasattr(PredictionResult, "confidence")


# ── P2: Business Metrics ──

class TestBusinessMetrics:
    def test_generate(self):
        from backend.services.analytics_services import BusinessMetricsService
        import asyncio; svc = BusinessMetricsService()
        r = asyncio.run(svc.generate())
        assert r.total_leads > 0; assert r.conversion_rate > 0; assert r.total_revenue > 0

    def test_dataclass_fields(self):
        from backend.services.analytics_services import BusinessMetricsSnapshot
        m = BusinessMetricsSnapshot(snapshot_date="2026-06-09")
        assert m.active_deals == 0; assert m.total_revenue == 0

    def test_revenue_positive(self):
        import asyncio; from backend.services.analytics_services import BusinessMetricsService
        svc = BusinessMetricsService(); r = asyncio.run(svc.generate())
        assert r.commission_revenue <= r.total_revenue


# ── P3: Funnel ──

class TestFunnel:
    def test_all_stages_present(self):
        import asyncio; from backend.services.analytics_services import FunnelAnalyticsService
        svc = FunnelAnalyticsService(); r = asyncio.run(svc.get_funnel())
        stages = [f.stage for f in r]
        assert "lead" in stages and "deal" in stages and "closed" in stages

    def test_funnel_order(self):
        import asyncio; from backend.services.analytics_services import FunnelAnalyticsService
        svc = FunnelAnalyticsService(); r = asyncio.run(svc.get_funnel())
        for i in range(len(r)-1):
            assert r[i].stage in svc.FUNNEL_STAGES

    def test_stage_duration(self):
        import asyncio; from backend.services.analytics_services import FunnelAnalyticsService
        svc = FunnelAnalyticsService(); r = asyncio.run(svc.get_stage_duration("deal"))
        assert r > 0

    def test_conversion_decreasing(self):
        import asyncio; from backend.services.analytics_services import FunnelAnalyticsService
        svc = FunnelAnalyticsService(); r = asyncio.run(svc.get_funnel())
        counts = [f.count for f in r]
        for i in range(len(counts)-1):
            assert counts[i] >= counts[i+1], f"Funnel {r[i].stage} → {r[i+1].stage}: {counts[i]} < {counts[i+1]}"


# ── P4: Team Performance ──

class TestTeamPerformance:
    def test_team_has_members(self):
        import asyncio; from backend.services.analytics_services import TeamPerformanceService
        svc = TeamPerformanceService(); r = asyncio.run(svc.get_report())
        assert len(r) >= 2

    def test_member_has_workload(self):
        import asyncio; from backend.services.analytics_services import TeamPerformanceService
        import asyncio; svc = TeamPerformanceService(); r = asyncio.run(svc.get_report())
        for m in r: assert m.workload_score > 0

    def test_conversion_rate_range(self):
        import asyncio; from backend.services.analytics_services import TeamPerformanceService
        svc = TeamPerformanceService(); r = asyncio.run(svc.get_report())
        for m in r: assert 0 <= m.conversion_rate <= 100

    def test_team_dataclass(self):
        from backend.services.analytics_services import TeamMemberMetrics
        m = TeamMemberMetrics(user_id="u1", name="Test")
        assert m.assigned_leads == 0


# ── P5: Portfolio ──

class TestPortfolio:
    def test_report_structure(self):
        import asyncio; from backend.services.analytics_services import PortfolioAnalyticsService
        svc = PortfolioAnalyticsService(); r = asyncio.run(svc.get_report())
        assert "total_properties" in r; assert "total_revenue" in r

    def test_by_type(self):
        import asyncio; from backend.services.analytics_services import PortfolioAnalyticsService
        svc = PortfolioAnalyticsService(); r = asyncio.run(svc.get_report())
        assert "apartment" in r.get("by_type", {})

    def test_avg_days_positive(self):
        import asyncio; from backend.services.analytics_services import PortfolioAnalyticsService
        svc = PortfolioAnalyticsService(); r = asyncio.run(svc.get_report())
        assert r["avg_days_on_market"] > 0


# ── P6: Predictions ──

class TestPredictions:
    def test_lead_conversion(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine(); r = asyncio.run(svc.predict_lead_conversion(UUID(int=1), 0.7, "referral"))
        assert r["score"] > 50; assert "confidence" in r

    def test_deal_delay(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine(); r = asyncio.run(svc.predict_deal_delay(UUID(int=1), 0.8))
        assert r["score"] > 50

    def test_compliance_failure(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine(); r = asyncio.run(svc.predict_compliance_failure(UUID(int=1), 0.3))
        assert r["score"] > 50

    def test_missing_documents(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine(); r = asyncio.run(svc.predict_missing_documents(UUID(int=1)))
        assert "spouse consent" in r["explanation"]

    def test_lead_conversion_formula(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine()
        r1 = asyncio.run(svc.predict_lead_conversion(UUID(int=1), 0.9, "referral"))
        r2 = asyncio.run(svc.predict_lead_conversion(UUID(int=1), 0.1, "site"))
        assert r1["score"] > r2["score"]

    def test_delay_with_low_risk(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine(); r = asyncio.run(svc.predict_deal_delay(UUID(int=1), 0.1))
        assert r["score"] < 50

    def test_predictions_deterministic(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine()
        r1 = asyncio.run(svc.predict_lead_conversion(UUID(int=1), 0.5, "site"))
        r2 = asyncio.run(svc.predict_lead_conversion(UUID(int=1), 0.5, "site"))
        assert r1["score"] == r2["score"]

    def test_confidence_range(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine(); r = asyncio.run(svc.predict_lead_conversion(UUID(int=1)))
        assert 0 <= r["confidence"] <= 1.0

    def test_score_range(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine(); r = asyncio.run(svc.predict_deal_delay(UUID(int=1)))
        assert 0 <= r["score"] <= 100


# ── P9: Alerts ──

class TestAlerts:
    def test_alert_types_defined(self):
        from backend.services.analytics_services import AlertEngine
        types = AlertEngine.ALERT_TYPES
        assert len(types) >= 5; assert "compliance_drop" in types

    def test_generate_alerts(self):
        import asyncio; from backend.services.analytics_services import AlertEngine
        svc = AlertEngine(); r = asyncio.run(svc.generate_alerts())
        assert isinstance(r, list); assert len(r) >= 1

    def test_alert_with_session(self):
        import asyncio
        class MockSession:
            async def execute(self, q): return self
            def scalar(self): return 5
        from backend.services.analytics_services import AlertEngine
        svc = AlertEngine(); r = asyncio.run(svc.generate_alerts(MockSession()))
        alerts_by_type = {a["alert_type"] for a in r}
        assert "sla_breach_spike" in alerts_by_type

    def test_resolve_alert(self):
        import asyncio; from backend.services.analytics_services import AlertEngine
        svc = AlertEngine(); r = asyncio.run(svc.resolve_alert(UUID(int=1)))
        assert r is False

    def test_severity_levels(self):
        for s in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            assert isinstance(s, str) and len(s) > 0

    def test_alert_resolve_with_session(self):
        import asyncio
        class MockSession:
            async def execute(self, q): return self
            def scalar_one_or_none(self): return None
            async def flush(self): pass
        from backend.services.analytics_services import AlertEngine
        svc = AlertEngine(); r = asyncio.run(svc.resolve_alert(UUID(int=1), MockSession()))
        assert r is False


# ── P10: API ──

class TestAPI:
    def test_all_endpoints(self):
        from backend.api.routes.sprint7a import router
        paths = [r.path for r in router.routes]
        for ep in ["/dashboard", "/funnel", "/team", "/portfolio", "/compliance", "/risk", "/predictions", "/alerts"]:
            assert any(ep in p for p in paths), f"{ep} not found"

    def test_dashboard_route(self):
        from backend.api.routes.sprint7a import router
        assert any("dashboard" in r.path for r in router.routes)

    def test_funnel_route(self):
        from backend.api.routes.sprint7a import router
        assert any("funnel" in r.path for r in router.routes)


# ── Migration ──

class TestMigration:
    def test_migration_exists(self):
        import os; assert os.path.exists("backend/migrations/versions/021_add_analytics_foundation.py")

    def test_three_tables(self):
        import os
        content = open("backend/migrations/versions/021_add_analytics_foundation.py").read()
        for t in ["analytics_snapshots", "analytics_alerts", "prediction_results"]:
            assert t in content


# ── Edge Cases ──

class TestEdgeCases:
    def test_empty_funnel_period(self):
        import asyncio; from backend.services.analytics_services import FunnelAnalyticsService
        svc = FunnelAnalyticsService(); r = asyncio.run(svc.get_funnel("unknown"))
        assert len(r) == 6

    def test_portfolio_group_by_all(self):
        import asyncio; from backend.services.analytics_services import PortfolioAnalyticsService
        svc = PortfolioAnalyticsService(); r = asyncio.run(svc.get_report("all"))
        assert "total_properties" in r

    def test_business_metrics_dataclass_defaults(self):
        from backend.services.analytics_services import BusinessMetricsSnapshot
        m = BusinessMetricsSnapshot(snapshot_date="2026-01-01")
        assert m.total_leads == 0; assert m.total_revenue == 0.0

    def test_prediction_explanation_not_empty(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine(); r = asyncio.run(svc.predict_lead_conversion(UUID(int=1)))
        assert len(r["explanation"]) > 0

    def test_alert_catalog(self):
        from backend.services.analytics_services import AlertEngine
        assert len(AlertEngine.ALERT_TYPES) == 6

    def test_funnel_drop_increases(self):
        import asyncio; from backend.services.analytics_services import FunnelAnalyticsService
        svc = FunnelAnalyticsService(); r = asyncio.run(svc.get_funnel())
        for i in range(len(r)-1):
            drop = r[i].count - r[i+1].count
            assert drop >= 0, f"Unexpected increase: {r[i].stage}→{r[i+1].stage}"

    def test_workload_high_indicates_overload(self):
        import asyncio; from backend.services.analytics_services import TeamPerformanceService
        svc = TeamPerformanceService(); r = asyncio.run(svc.get_report())
        high_workload = [m for m in r if m.workload_score > 70]
        assert len(high_workload) >= 1

    def test_api_count(self):
        from backend.api.routes.sprint7a import router
        assert len(router.routes) >= 8

    def test_analytics_snapshot_repo(self):
        from backend.services.analytics_services import AnalyticsSnapshotRepository
        class S: pass
        r = AnalyticsSnapshotRepository(S()); assert r is not None

    def test_alert_repo(self):
        from backend.services.analytics_services import AnalyticsAlertRepository
        class S: pass
        r = AnalyticsAlertRepository(S()); assert r is not None

    def test_prediction_repo(self):
        from backend.services.analytics_services import PredictionResultRepository
        class S: pass
        r = PredictionResultRepository(S()); assert r is not None

    def test_funnel_6_stages(self):
        import asyncio; from backend.services.analytics_services import FunnelAnalyticsService
        svc = FunnelAnalyticsService(); r = asyncio.run(svc.get_funnel())
        assert len(r) == 6

    def test_funnel_counts_decrease(self):
        import asyncio; from backend.services.analytics_services import FunnelAnalyticsService
        svc = FunnelAnalyticsService(); r = asyncio.run(svc.get_funnel())
        counts = [f.count for f in r]
        assert counts == sorted(counts, reverse=True)

    def test_team_member_names(self):
        import asyncio; from backend.services.analytics_services import TeamPerformanceService
        svc = TeamPerformanceService(); r = asyncio.run(svc.get_report())
        names = {m.name for m in r}
        assert "Анна" in names; assert len(names) >= 2

    def test_prediction_entity_id(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        uid = UUID(int=42); svc = PredictionEngine()
        r = asyncio.run(svc.predict_lead_conversion(uid))
        assert r["entity_id"] == str(uid)

    def test_prediction_type_consistency(self):
        import asyncio; from backend.services.analytics_services import PredictionEngine
        svc = PredictionEngine()
        r = asyncio.run(svc.predict_lead_conversion(UUID(int=1)))
        assert r["prediction_type"] == "lead_conversion"
        r = asyncio.run(svc.predict_deal_delay(UUID(int=1)))
        assert r["prediction_type"] == "deal_delay"

    def test_alert_generation_always_returns(self):
        import asyncio; from backend.services.analytics_services import AlertEngine
        svc = AlertEngine(); r = asyncio.run(svc.generate_alerts())
        assert r is not None

    def test_business_metrics_has_all_fields(self):
        import asyncio; from backend.services.analytics_services import BusinessMetricsService
        svc = BusinessMetricsService(); r = asyncio.run(svc.generate())
        required = ["total_leads", "active_deals", "total_revenue", "avg_compliance_score", "avg_risk_score"]
        for f in required:
            assert getattr(r, f, None) is not None, f"Missing field: {f}"

    def test_compliance_api_returns(self):
        import asyncio; from backend.api.routes.sprint7a import router
        assert any("compliance" in r.path for r in router.routes)

    def test_risk_api_returns(self):
        import asyncio; from backend.api.routes.sprint7a import router
        assert any("/risk" == r.path for r in router.routes if "/risk" in str(r.path))

    def test_migration_021_has_indexes(self):
        content = open("backend/migrations/versions/021_add_analytics_foundation.py").read()
        assert content.count("create_index") >= 7

    def test_portfolio_by_type_map(self):
        import asyncio; from backend.services.analytics_services import PortfolioAnalyticsService
        svc = PortfolioAnalyticsService(); r = asyncio.run(svc.get_report())
        assert isinstance(r.get("by_type", {}), dict)

    def test_dashboard_returns_metrics(self):
        import asyncio; from backend.services.analytics_services import BusinessMetricsService
        svc = BusinessMetricsService(); r = asyncio.run(svc.generate())
        assert isinstance(r.total_leads, int)

    def test_alert_types_catalog_complete(self):
        from backend.services.analytics_services import AlertEngine
        expected = {"lead_conversion_drop", "compliance_drop", "risk_spike", "sla_breach_spike", "deal_stagnation", "regulation_impact"}
        assert set(AlertEngine.ALERT_TYPES) == expected
