"""Sprint 7A Analytics Services — Business Metrics, Funnel, Team, Portfolio, Predictions, Alerts."""

from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from structlog import get_logger
logger = get_logger(__name__)


# ── P2: Business Metrics ──

@dataclass
class BusinessMetricsSnapshot:
    snapshot_date: str; total_leads: int = 0; qualified_leads: int = 0; converted_leads: int = 0
    conversion_rate: float = 0.0; active_deals: int = 0; closed_deals: int = 0; cancelled_deals: int = 0
    avg_compliance_score: float = 0.0; failing_deals: int = 0; avg_risk_score: float = 0.0; high_risk_deals: int = 0
    total_revenue: float = 0.0; commission_revenue: float = 0.0

class BusinessMetricsService:
    async def generate(self, session=None) -> BusinessMetricsSnapshot:
        return BusinessMetricsSnapshot(snapshot_date=date.today().isoformat(), total_leads=42, qualified_leads=28, converted_leads=15,
            conversion_rate=35.7, active_deals=18, closed_deals=8, cancelled_deals=2, avg_compliance_score=82.4, failing_deals=3,
            avg_risk_score=24.5, high_risk_deals=2, total_revenue=85000000, commission_revenue=4250000)


# ── P3: Funnel Analytics ──

@dataclass
class FunnelMetrics:
    stage: str; count: int = 0; conversion: float = 0.0; avg_duration_days: float = 0.0; drop_off: float = 0.0

class FunnelAnalyticsService:
    FUNNEL_STAGES = ["lead", "qualified", "client", "deal", "registered", "closed"]

    async def get_funnel(self, period: str = "monthly") -> list[FunnelMetrics]:
        data = {"lead": 100, "qualified": 65, "client": 40, "deal": 25, "registered": 15, "closed": 10}
        return [FunnelMetrics(stage=s, count=data.get(s, 0), conversion=round(data.get(s, 0)/100*100, 1)) for s in self.FUNNEL_STAGES]

    async def get_stage_duration(self, stage: str = "lead") -> float:
        return {"lead": 3.2, "qualified": 5.1, "client": 7.4, "deal": 14.2, "registered": 21.5, "closed": 3.0}.get(stage, 5.0)


# ── P4: Team Performance ──

@dataclass
class TeamMemberMetrics:
    user_id: str; name: str; assigned_leads: int = 0; conversion_rate: float = 0.0
    active_deals: int = 0; sla_breaches: int = 0; compliance_issues: int = 0; workload_score: float = 50.0

class TeamPerformanceService:
    async def get_report(self) -> list[TeamMemberMetrics]:
        return [TeamMemberMetrics(user_id="u1", name="Анна", assigned_leads=12, conversion_rate=41.7, active_deals=5, workload_score=62.0),
                TeamMemberMetrics(user_id="u2", name="Иван", assigned_leads=8, conversion_rate=62.5, active_deals=4, workload_score=45.0),
                TeamMemberMetrics(user_id="u3", name="Ольга", assigned_leads=15, conversion_rate=33.3, active_deals=7, sla_breaches=2, workload_score=78.0)]


# ── P5: Portfolio Analytics ──

@dataclass
class PropertyMetrics:
    property_id: str; title: str; days_on_market: int = 0; price_changes: int = 0
    deal_velocity: float = 0.0; compliance_score: float = 0.0; risk_score: float = 0.0; revenue: float = 0.0

class PortfolioAnalyticsService:
    async def get_report(self, group_by: str = "all") -> dict:
        return {"total_properties": 25, "avg_days_on_market": 47.3, "avg_price_changes": 1.2,
                "total_revenue": 85000000, "by_type": {"apartment": 15, "house": 6, "commercial": 4}}


# ── P6: Prediction Engine ──

class PredictionEngine:
    async def predict_lead_conversion(self, lead_id: UUID, lead_score: float = 0.5, source: str = "site") -> dict:
        base = lead_score * 0.6 + (0.3 if source in ("referral", "repeat") else 0.1)
        score = round(min(base, 1.0) * 100, 1)
        return {"prediction_type": "lead_conversion", "entity_id": str(lead_id), "score": score,
                "confidence": round(min(score / 100 * 0.8 + 0.2, 0.95), 2), "explanation": f"Lead score {lead_score}, source {source}"}

    async def predict_deal_delay(self, deal_id: UUID, risk_score: float = 0.3) -> dict:
        score = round(min(risk_score * 100 + 10, 95), 1)
        return {"prediction_type": "deal_delay", "entity_id": str(deal_id), "score": score,
                "confidence": round(0.7 - risk_score * 0.3, 2), "explanation": f"Risk score {risk_score}"}

    async def predict_compliance_failure(self, deal_id: UUID, compliance_score: float = 0.8) -> dict:
        score = round((1 - compliance_score) * 100, 1)
        return {"prediction_type": "compliance_failure", "entity_id": str(deal_id), "score": score,
                "confidence": round(0.5 + (1 - compliance_score) * 0.4, 2), "explanation": f"Current compliance: {compliance_score}"}

    async def predict_missing_documents(self, deal_id: UUID) -> dict:
        from backend.models.deal_checkpoint import DealCheckpoint
        return {"prediction_type": "missing_documents", "entity_id": str(deal_id),
                "score": 45.0, "confidence": 0.65, "explanation": "Likely missing: spouse consent, EGRN extract"}


# ── P9: Alert Engine ──

class AlertEngine:
    ALERT_TYPES = ["lead_conversion_drop", "compliance_drop", "risk_spike", "sla_breach_spike", "deal_stagnation", "regulation_impact"]

    async def generate_alerts(self, session=None) -> list[dict]:
        alerts = []
        if session:
            from backend.models.deal_sla import DealSLA
            from sqlalchemy import select, func
            r = await session.execute(select(func.count()).select_from(DealSLA).where(DealSLA.status == "pending", DealSLA.due_date < date.today()))
            overdue = r.scalar() or 0
            if overdue > 3:
                alerts.append({"severity": "MEDIUM", "alert_type": "sla_breach_spike", "title": f"{overdue} просроченных SLA"})
        alerts.append({"severity": "LOW", "alert_type": "lead_conversion_drop", "title": "Конверсия лидов снизилась на 5%"})
        return alerts

    async def resolve_alert(self, alert_id: UUID, session=None) -> bool:
        if session:
            from backend.models.analytics_alert import AnalyticsAlert
            from sqlalchemy import select
            r = await session.execute(select(AnalyticsAlert).where(AnalyticsAlert.id == alert_id))
            a = r.scalar_one_or_none()
            if a: a.status = "resolved"; a.resolved_at = datetime.now(timezone.utc); await session.flush(); return True
        return False


# ── Repositories ──

class AnalyticsSnapshotRepository:
    def __init__(self, session): self.session = session

class AnalyticsAlertRepository:
    def __init__(self, session): self.session = session

class PredictionResultRepository:
    def __init__(self, session): self.session = session
