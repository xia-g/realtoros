"""Sprint 6A Regulatory Intelligence — API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session

router = APIRouter(prefix="/api/v1/regulations", tags=["regulatory-intelligence"])


class SourceResponse(BaseModel):
    code: str
    name: str
    source_type: str


class SyncResponse(BaseModel):
    source: str
    documents_found: int
    status: str


class ChangeResponse(BaseModel):
    regulation_id: str
    change_type: str
    summary: str
    impact_level: str


class ImpactResponse(BaseModel):
    regulation_id: str
    impact_level: str
    summary: str
    affected_deals_count: int


class RecheckResponse(BaseModel):
    deal_id: str
    compliance_score: float
    status: str


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(session: AsyncSession = Depends(get_session)):
    from backend.services.regulation_source_service import RegulationSourceService
    svc = RegulationSourceService(session)
    return await svc.get_active_sources()


@router.post("/sync")
async def trigger_sync(session: AsyncSession = Depends(get_session)):
    from backend.services.regulation_sync_service_v2 import RegulationSyncServiceV2
    import uuid
    svc = RegulationSyncServiceV2(session)
    results = await svc.sync_all_sources(correlation_id=str(uuid.uuid4()))
    return {"results": results}


@router.get("/changes")
async def get_changes(session: AsyncSession = Depends(get_session)):
    from backend.models.regulation_change_event import RegulationChangeEvent
    from sqlalchemy import select
    result = await session.execute(
        select(RegulationChangeEvent).order_by(RegulationChangeEvent.detected_at.desc()).limit(20)
    )
    events = result.scalars().all()
    return [
        {"regulation_id": str(e.regulation_id), "change_type": e.change_type, "summary": e.summary, "impact_level": e.impact_level}
        for e in events
    ]


@router.post("/impact/{regulation_id}")
async def analyze_impact(regulation_id: str, session: AsyncSession = Depends(get_session)):
    from backend.services.regulation_impact_service_v2 import RegulationImpactServiceV2
    from uuid import UUID
    svc = RegulationImpactServiceV2(session)
    result = await svc.evaluate_regulation_change(UUID(regulation_id), "Impact analysis triggered")
    return result


@router.post("/recheck")
async def recheck_all(session: AsyncSession = Depends(get_session)):
    from backend.services.compliance_service import ComplianceService
    from backend.models.deal_workflow import DealWorkflow
    from sqlalchemy import select
    import uuid

    result = await session.execute(select(DealWorkflow).where(DealWorkflow.deleted_at.is_(None)))
    workflows = result.scalars().all()
    svc = ComplianceService()
    results = []
    for wf in workflows[:10]:
        r = await svc.generate_compliance_report(wf.deal_id, wf.workflow_type)
        results.append({"deal_id": str(wf.deal_id), "compliance_score": r["compliance_score"], "status": r["status"]})
    return {"deals_rechecked": len(results), "results": results}
