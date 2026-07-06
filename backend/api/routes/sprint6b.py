"""Sprint 6B Deal Operations Platform — API (25+ endpoints)."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.dependencies import get_session

router = APIRouter(prefix="/api/v1", tags=["deal-operations"])


# ── Schemas ──
class PlaybookResponse(BaseModel):
    code: str; name: str; deal_type: str; version: str

class StakeholderRequest(BaseModel):
    stakeholder_type: str; name: str; organization: str = ""; responsibilities: list[str] = []

class ActionRequest(BaseModel):
    action_type: str; title: str; priority: str = "medium"; assigned_to: str = ""

class ValidateDocsRequest(BaseModel):
    document_ids: list[str]


# ── P1: Playbooks ──
@router.get("/playbooks/{code}")
async def get_playbook(code: str, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import PlaybookService
    svc = PlaybookService(session)
    pb = await svc.get_playbook(code)
    if not pb: raise HTTPException(404, "Playbook not found")
    return pb

@router.get("/playbooks")
async def list_playbooks(session: AsyncSession = Depends(get_session)):
    from backend.models.deal_playbook import DealPlaybook
    from sqlalchemy import select
    r = await session.execute(select(DealPlaybook).where(DealPlaybook.is_active.is_(True)))
    return [{"code": p.code, "name": p.name, "deal_type": p.deal_type} for p in r.scalars().all()]

@router.get("/playbooks/{code}/stages")
async def get_playbook_stages(code: str, session: AsyncSession = Depends(get_session)):
    from backend.models.deal_playbook import DealPlaybook, DealPlaybookStage
    from sqlalchemy import select
    r = await session.execute(select(DealPlaybook).where(DealPlaybook.code == code))
    pb = r.scalar_one_or_none()
    if not pb: raise HTTPException(404)
    r2 = await session.execute(select(DealPlaybookStage).where(DealPlaybookStage.playbook_id == pb.id).order_by(DealPlaybookStage.sequence))
    return [{"stage_key": s.stage_key, "name": s.name, "sequence": s.sequence, "sla_days": s.sla_days} for s in r2.scalars().all()]


# ── P2: SLA ──
@router.get("/sla/overdue")
async def get_overdue_slas(session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import SLAService
    svc = SLAService(session)
    return await svc.find_overdue()

@router.get("/sla/{deal_id}")
async def get_deal_slas(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.models.deal_sla import DealSLA
    from sqlalchemy import select
    r = await session.execute(select(DealSLA).where(DealSLA.deal_id == deal_id))
    return [{"stage_key": s.stage_key, "due_date": s.due_date.isoformat(), "status": s.status} for s in r.scalars().all()]

@router.post("/sla/{deal_id}/create")
async def create_deal_sla(deal_id: UUID, stage_key: str = "", sla_days: int = 14, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import SLAService
    svc = SLAService(session)
    return await svc.create_sla(deal_id, stage_key, sla_days)


# ── P3: Timeline ──
@router.get("/timeline/{deal_id}")
async def get_timeline(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import TimelineService
    svc = TimelineService(session)
    return await svc.get_timeline(deal_id)


# ── P4: Stakeholders ──
@router.get("/stakeholders/{deal_id}")
async def get_stakeholders(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import StakeholderService
    svc = StakeholderService(session)
    return await svc.get_stakeholders(deal_id)

@router.post("/stakeholders/{deal_id}")
async def add_stakeholder(deal_id: UUID, body: StakeholderRequest, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import StakeholderService
    svc = StakeholderService(session)
    return await svc.add_stakeholder(deal_id, body.stakeholder_type, body.name, organization=body.organization, responsibilities=body.responsibilities)


# ── P5: Document Validation ──
@router.post("/document-validation")
async def validate_documents(body: ValidateDocsRequest, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import DocumentValidationService
    svc = DocumentValidationService(session)
    return await svc.validate_package([UUID(d) for d in body.document_ids])


# ── P6: Health ──
@router.get("/health/{deal_id}")
async def get_deal_health(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import DealHealthService
    svc = DealHealthService(session)
    return await svc.calculate_health(deal_id)

@router.get("/health/{deal_id}/latest")
async def get_latest_health(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.models.deal_health_snapshot import DealHealthSnapshot
    from sqlalchemy import select
    r = await session.execute(select(DealHealthSnapshot).where(DealHealthSnapshot.deal_id == deal_id).order_by(DealHealthSnapshot.calculated_at.desc()).limit(1))
    hs = r.scalar_one_or_none()
    if not hs: raise HTTPException(404)
    return {"score": hs.score, "level": "healthy" if hs.score >= 90 else "attention" if hs.score >= 70 else "critical",
            "compliance_score": hs.compliance_score, "risk_score": hs.risk_score, "sla_score": hs.sla_score,
            "document_score": hs.document_score, "activity_score": hs.activity_score}


# ── P7: Actions ──
@router.get("/actions/{deal_id}")
async def get_deal_actions(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import ActionEngineService
    svc = ActionEngineService(session)
    health_svc = __import__("backend.services.deal_operations_services", fromlist=["DealHealthService"]).DealHealthService(session)
    health = await health_svc.calculate_health(deal_id)
    return await svc.generate_actions(deal_id, health)

@router.get("/actions/{deal_id}/next-steps")
async def get_next_steps(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import ActionEngineService
    svc = ActionEngineService(session)
    return await svc.recommend_next_steps(deal_id)


# ── Copilot ──
@router.get("/copilot/deal-readiness/{deal_id}")
async def deal_readiness(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.compliance_service import ComplianceService
    from backend.services.deal_operations_services import DealHealthService
    health_svc = DealHealthService(session)
    comp = ComplianceService()
    compliance = await comp.generate_compliance_report(deal_id, "SALE_APARTMENT")
    health = await health_svc.calculate_health(deal_id,
        compliance_score=compliance["compliance_score"],
        sla_score=100, document_score=compliance["compliance_score"])
    return {"health_score": health["score"], "level": health["level"], "compliance_score": compliance["compliance_score"],
            "blocking_issues": compliance.get("blocking_issues", []), "registration_ready": compliance.get("registration_readiness", False)}

@router.get("/copilot/deal-summary/{deal_id}")
async def deal_summary(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    from backend.services.deal_operations_services import TimelineService, StakeholderService, DealHealthService
    t = TimelineService(session); s = StakeholderService(session); h = DealHealthService(session)
    timeline = await t.get_timeline(deal_id, 5)
    stakeholders = await s.get_stakeholders(deal_id)
    health = await h.calculate_health(deal_id)
    return {"health": health, "recent_events": timeline, "stakeholders": stakeholders}
