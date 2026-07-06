"""Sprint 5 Deal Lifecycle & Compliance Platform — API routes.

Prefix: /api/v1/deals/{deal_id}/workflow
Prefix: /api/v1/deals/{deal_id}/compliance
Prefix: /api/v1/deals/{deal_id}/risk
Prefix: /api/v1/regulations
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session

# ─── Routers ───

workflow_router = APIRouter(prefix="/api/v1/deals/{deal_id}/workflow", tags=["deal-workflow"])
compliance_router = APIRouter(prefix="/api/v1/deals/{deal_id}/compliance", tags=["deal-compliance"])
risk_router = APIRouter(prefix="/api/v1/deals/{deal_id}/risk", tags=["deal-risk"])
regulation_router = APIRouter(prefix="/api/v1/regulations", tags=["regulations"])


# ─── Schemas ───


class StartWorkflowRequest(BaseModel):
    workflow_type: str = "SALE_APARTMENT"


class AdvanceWorkflowRequest(BaseModel):
    notes: str = ""


class ComplianceQuery(BaseModel):
    deal_type: str = "SALE_APARTMENT"
    completed_checkpoints: str = ""
    uploaded_documents: str = ""


# ─── Workflow Endpoints ───


@workflow_router.post("/start")
async def start_workflow(deal_id: UUID, body: StartWorkflowRequest, session: AsyncSession = Depends(get_session)):
    from backend.services.workflow_service import WorkflowService
    svc = WorkflowService(session)
    wf = await svc.start_workflow(deal_id, body.workflow_type)
    return {"workflow_id": str(wf.id), "current_stage": wf.current_stage, "status": wf.status}


@workflow_router.post("/advance")
async def advance_workflow(deal_id: UUID, body: AdvanceWorkflowRequest, session: AsyncSession = Depends(get_session)):
    from backend.services.workflow_service import WorkflowService
    svc = WorkflowService(session)
    wf = await svc.get_workflow(deal_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf = await svc.advance_stage(wf.id, notes=body.notes)
    if not wf:
        raise HTTPException(status_code=400, detail="Cannot advance — already at final stage or workflow inactive")
    return {"workflow_id": str(wf.id), "current_stage": wf.current_stage, "status": wf.status}


@workflow_router.get("")
async def get_workflow(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.workflow_service import WorkflowService
    svc = WorkflowService(session)
    wf = await svc.get_workflow(deal_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"workflow_id": str(wf.id), "workflow_type": wf.workflow_type, "current_stage": wf.current_stage, "status": wf.status, "started_at": wf.started_at.isoformat() if wf.started_at else None, "completed_at": wf.completed_at.isoformat() if wf.completed_at else None}


# ─── Compliance Endpoints ───


@compliance_router.get("")
async def get_compliance(deal_id: UUID, deal_type: str = "SALE_APARTMENT", session: AsyncSession = Depends(get_session)):
    from backend.services.compliance_service import ComplianceService
    svc = ComplianceService()
    result = await svc.generate_compliance_report(deal_id, deal_type)
    return result


@compliance_router.get("/completeness")
async def get_completeness(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.document_package_service import DocumentPackageService
    svc = DocumentPackageService(session)
    result = await svc.calculate_completeness(deal_id)
    return result


# ─── Risk Endpoints ───


@risk_router.get("")
async def get_deal_risk(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.risk_assessment_service import RiskAssessmentService
    svc = RiskAssessmentService(session)
    result = await svc.evaluate_deal(deal_id)
    return result


# ─── Regulation Endpoints ───


@regulation_router.get("/search")
async def search_regulations(q: str = "", min_trust: str = "COMMUNITY", session: AsyncSession = Depends(get_session)):
    from backend.services.regulation_service import RegulationService
    svc = RegulationService()
    results = await svc.search_regulations(query=q, min_trust=min_trust, limit=20)
    return {"results": results}


@regulation_router.get("/{regulation_id}")
async def get_regulation(regulation_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.regulation_service import RegulationService
    svc = RegulationService()
    result = await svc.get_regulation(regulation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return result
