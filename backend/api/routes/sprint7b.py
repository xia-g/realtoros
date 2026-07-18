"""Sprint 7B Executive Dashboard & Command Center — API."""

from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.dependencies import get_session

router = APIRouter(prefix="/api/v1/executive", tags=["executive"])


class DashboardResponse(BaseModel):
    revenue: float; active_deals: int; active_clients: int; lead_conversion: float
    compliance_score: float; risk_score: float; critical_alerts: int

class WarRoomResponse(BaseModel):
    title: str; severity: str


@router.get("/dashboard")
async def dashboard():
    from backend.services.executive_services import ExecutiveDashboardService
    svc = ExecutiveDashboardService()
    return await svc.get_dashboard()

@router.get("/summary")
async def summary():
    from backend.services.executive_services import ExecutiveDashboardService
    svc = ExecutiveDashboardService()
    return await svc.get_executive_summary()

@router.get("/operations")
async def operations():
    from backend.services.executive_services import OperationsCenterService
    svc = OperationsCenterService()
    return await svc.get_snapshot()

@router.get("/warrooms")
async def warrooms():
    from backend.services.executive_services import WarRoomService
    svc = WarRoomService()
    return await svc.get_war_rooms()

@router.get("/risks")
async def risks():
    from backend.services.executive_services import ExecutiveCopilot
    svc = ExecutiveCopilot()
    return await svc.get_risk_summary()

@router.get("/compliance")
async def compliance():
    from backend.services.executive_services import ExecutiveCopilot
    svc = ExecutiveCopilot()
    return await svc.get_compliance_summary()

@router.get("/team")
async def team():
    from backend.services.executive_services import ExecutiveCopilot
    svc = ExecutiveCopilot()
    return await svc.get_team_summary()

@router.get("/revenue")
async def revenue():
    from backend.services.executive_services import ExecutiveCopilot
    svc = ExecutiveCopilot()
    return await svc.get_revenue_summary()

@router.get("/regulations")
async def regulations():
    return {"changes": 1, "critical": 0, "high": 1, "recent": [{"title": "218-ФЗ новая редакция", "impact": "HIGH"}]}

@router.get("/critical")
async def critical():
    return {"critical_alerts": 2, "critical_risks": 1, "critical_sla": 2, "critical_deals": 3}

@router.post("/warroom")
async def create_warroom(title: str = "", severity: str = "MEDIUM"):
    from backend.services.executive_services import WarRoomService
    svc = WarRoomService()
    return await svc.create_war_room(title, severity)

@router.get("/priority")
async def priority():
    from backend.services.executive_services import ExecutiveDashboardService
    svc = ExecutiveDashboardService()
    return await svc.get_priority_items()

@router.get("/health-overview")
async def health_overview():
    from backend.services.executive_services import ExecutiveDashboardService
    svc = ExecutiveDashboardService()
    return await svc.get_health_overview()

@router.post("/analyze")
async def analyze(question: str = ""):
    from backend.services.executive_services import ExecutiveCopilot
    svc = ExecutiveCopilot()
    return await svc.analyze(question)
