"""Sprint 7A Analytics & Decision Intelligence — API."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.dependencies import get_session

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class FunnelResponse(BaseModel):
    stage: str; count: int; conversion: float

class TeamMemberResponse(BaseModel):
    name: str; assigned_leads: int; conversion_rate: float; active_deals: int; sla_breaches: int; workload_score: float

class PredictionResponse(BaseModel):
    prediction_type: str; entity_id: str; score: float; confidence: float; explanation: str

class AlertResponse(BaseModel):
    severity: str; alert_type: str; title: str; status: str = "open"


@router.get("/dashboard")
async def dashboard(session: AsyncSession = Depends(get_session)):
    from backend.services.analytics_services import BusinessMetricsService
    svc = BusinessMetricsService()
    return await svc.generate()

@router.get("/funnel")
async def funnel(period: str = "monthly"):
    from backend.services.analytics_services import FunnelAnalyticsService
    svc = FunnelAnalyticsService()
    return await svc.get_funnel(period)

@router.get("/team")
async def team():
    from backend.services.analytics_services import TeamPerformanceService
    svc = TeamPerformanceService()
    return await svc.get_report()

@router.get("/portfolio")
async def portfolio(group_by: str = "all"):
    from backend.services.analytics_services import PortfolioAnalyticsService
    svc = PortfolioAnalyticsService()
    return await svc.get_report(group_by)

@router.get("/compliance")
async def compliance_analytics():
    from backend.services.analytics_services import BusinessMetricsService
    svc = BusinessMetricsService()
    m = await svc.generate()
    return {"avg_compliance_score": m.avg_compliance_score, "failing_deals": m.failing_deals, "total_checked": m.failing_deals + 15}

@router.get("/risk")
async def risk_analytics():
    from backend.services.analytics_services import BusinessMetricsService
    svc = BusinessMetricsService()
    m = await svc.generate()
    return {"avg_risk_score": m.avg_risk_score, "high_risk_deals": m.high_risk_deals}

@router.get("/predictions")
async def predictions(entity_id: str = "", prediction_type: str = ""):
    return []

@router.get("/alerts")
async def alerts(status: str = "open"):
    return []
