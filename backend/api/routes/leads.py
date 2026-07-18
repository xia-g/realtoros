"""Lead management API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session
from backend.schemas.lead import LeadCreate, LeadUpdate, LeadResponse
from backend.services.lead_service import LeadService

router = APIRouter()


@router.post("", response_model=LeadResponse)
async def create_lead(body: LeadCreate, session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    lead = await svc.create_lead(**body.model_dump(exclude_none=True))
    return lead


@router.get("", response_model=list[LeadResponse])
async def list_leads(session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    leads, _ = await svc.lead_repo.list(page=1, page_size=100)
    return leads


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    lead = await svc.lead_repo.get(lead_id)
    if lead is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: UUID, body: LeadUpdate, session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    lead = await svc.lead_repo.update(lead_id, **body.model_dump(exclude_none=True))
    if lead is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    await svc.archive_lead(lead_id)


@router.post("/{lead_id}/assign", response_model=LeadResponse)
async def assign_lead(lead_id: UUID, user_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    return await svc.assign_lead(lead_id, user_id)


@router.post("/{lead_id}/score", response_model=LeadResponse)
async def score_lead(lead_id: UUID, score: float, session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    return await svc.score_lead(lead_id, score)


@router.post("/{lead_id}/qualify", response_model=LeadResponse)
async def qualify_lead(lead_id: UUID, qualified_by: UUID, priority: str = "warm",
                       session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    return await svc.qualify_lead(lead_id, qualified_by, priority=priority)


@router.post("/{lead_id}/close")
async def close_lead(lead_id: UUID, status: str = "lost", session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    lead = await svc.change_status(lead_id, status)
    return {"lead_id": str(lead.id), "status": lead.status}


@router.post("/{lead_id}/convert")
async def convert_lead(lead_id: UUID, converted_by: UUID, create_deal: bool = False,
                       session: AsyncSession = Depends(get_session)):
    svc = LeadService(session)
    result = await svc.convert_lead(lead_id, converted_by=converted_by, create_deal=create_deal)
    return {
        "lead_id": str(result.lead.id),
        "client_id": str(result.client.id),
        "deal_id": str(result.deal.id) if result.deal else None,
    }
