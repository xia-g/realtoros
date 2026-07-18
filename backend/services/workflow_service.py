"""Workflow Service — управляемый жизненный цикл сделки."""

from __future__ import annotations
from uuid import UUID
from datetime import datetime, timezone
from structlog import get_logger
from sqlalchemy import select
from backend.models.deal_workflow import DealWorkflow, DealStageTransition

logger = get_logger(__name__)

DEAL_STAGES = ["LEAD", "PROPERTY_SELECTION", "NEGOTIATION", "ADVANCE_PAYMENT",
               "DOCUMENT_COLLECTION", "BANK_APPROVAL", "SIGNING", "REGISTRATION",
               "TRANSFER", "CLOSED"]

STAGE_CHECKPOINTS = {
    "LEAD": ["client_verified", "object_verified"],
    "PROPERTY_SELECTION": ["ownership_verified"],
    "NEGOTIATION": [],
    "ADVANCE_PAYMENT": ["deposit_received"],
    "DOCUMENT_COLLECTION": ["seller_documents", "bank_documents"],
    "BANK_APPROVAL": ["mortgage_approval", "income_confirmation"],
    "SIGNING": ["contract_signed", "transfer_act_signed"],
    "REGISTRATION": ["rosreestr_submitted", "registration_completed"],
    "TRANSFER": [],
    "CLOSED": [],
}

class WorkflowService:
    def __init__(self, session):
        self.session = session

    async def start_workflow(self, deal_id: UUID, workflow_type: str = "SALE_APARTMENT", user_id: UUID | None = None) -> DealWorkflow:
        wf = DealWorkflow(deal_id=deal_id, workflow_type=workflow_type, current_stage="LEAD", created_by=user_id)
        self.session.add(wf)
        await self.session.flush()
        logger.info("workflow_started", deal_id=str(deal_id), workflow_id=str(wf.id))
        return wf

    async def advance_stage(self, workflow_id: UUID, user_id: UUID | None = None, notes: str = "") -> DealWorkflow | None:
        result = await self.session.execute(select(DealWorkflow).where(DealWorkflow.id == workflow_id, DealWorkflow.deleted_at.is_(None)))
        wf = result.scalar_one_or_none()
        if not wf or wf.status != "active":
            return None
        stages = DEAL_STAGES
        try:
            idx = stages.index(wf.current_stage)
        except ValueError:
            return None
        if idx >= len(stages) - 1:
            return None
        to_stage = stages[idx + 1]
        transition = DealStageTransition(workflow_id=workflow_id, from_stage=wf.current_stage, to_stage=to_stage, transitioned_by=user_id, notes=notes or None)
        self.session.add(transition)
        wf.current_stage = to_stage
        wf.updated_by = user_id
        if to_stage == "CLOSED":
            wf.status = "completed"
            wf.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        logger.info("workflow_advanced", workflow_id=str(workflow_id), stage=to_stage)
        return wf

    async def rollback_stage(self, workflow_id: UUID, user_id: UUID | None = None, notes: str = "") -> DealWorkflow | None:
        result = await self.session.execute(select(DealWorkflow).where(DealWorkflow.id == workflow_id, DealWorkflow.deleted_at.is_(None)))
        wf = result.scalar_one_or_none()
        if not wf or wf.status != "active":
            return None
        stages = DEAL_STAGES
        try:
            idx = stages.index(wf.current_stage)
        except ValueError:
            return None
        if idx <= 0:
            return None
        to_stage = stages[idx - 1]
        transition = DealStageTransition(workflow_id=workflow_id, from_stage=wf.current_stage, to_stage=to_stage, conditions_met=False, notes=notes or None)
        self.session.add(transition)
        wf.current_stage = to_stage
        wf.updated_by = user_id
        await self.session.flush()
        return wf

    async def get_workflow(self, deal_id: UUID) -> DealWorkflow | None:
        result = await self.session.execute(
            select(DealWorkflow).where(DealWorkflow.deal_id == deal_id, DealWorkflow.deleted_at.is_(None)).order_by(DealWorkflow.created_at.desc())
        )
        return result.scalar_one_or_none()

    def get_stage_requirements(self, stage: str) -> list[str]:
        return STAGE_CHECKPOINTS.get(stage, [])

    def validate_transition(self, from_stage: str, to_stage: str) -> bool:
        stages = DEAL_STAGES
        try:
            return stages.index(to_stage) == stages.index(from_stage) + 1
        except (ValueError, IndexError):
            return False