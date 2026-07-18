"""Sprint 8 Autonomous Operations Platform — API."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.dependencies import get_session

router = APIRouter(prefix="/api/v1/autonomous", tags=["autonomous"])


class TaskResponse(BaseModel):
    problem: str; action: str; priority: str; owner_role: str

class EscalationResponse(BaseModel):
    assignee: str; reason: str; status: str

class RecoveryPlanResponse(BaseModel):
    deal_id: str; success_probability: float; status: str


@router.get("/tasks/{deal_id}")
async def generate_tasks(deal_id: UUID):
    from backend.services.autonomous_services import TaskOrchestrator
    svc = TaskOrchestrator(); tasks = await svc.generate_tasks(deal_id)
    return [{"problem": t.problem, "action": t.action, "priority": t.priority, "owner_role": t.owner_role} for t in tasks]

@router.post("/tasks/assign")
async def assign_task(task_id: str = "", strategy: str = "LEAST_LOADED"):
    from backend.services.autonomous_services import TaskOrchestrator, AssignmentService
    t = TaskOrchestrator(); tasks = await t.generate_tasks(UUID(int=1))
    if not tasks: raise HTTPException(404, "No tasks")
    svc = AssignmentService(); r = await svc.assign(tasks[0], strategy)
    return {"task_id": r.task_id, "assignee": r.assignee, "confidence": r.confidence, "reasoning": r.reasoning}

@router.get("/escalations")
async def get_escalations():
    from backend.services.autonomous_services import EscalationService
    svc = EscalationService(); return await svc.get_active()

@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(escalation_id: UUID):
    from backend.services.autonomous_services import EscalationService
    svc = EscalationService(); r = await svc.resolve(escalation_id)
    return {"resolved": r}

@router.get("/recovery/{deal_id}")
async def get_recovery_plan(deal_id: UUID):
    from backend.services.autonomous_services import DealRecoveryEngine
    svc = DealRecoveryEngine(); return await svc.generate_plan(deal_id)

@router.get("/recovery/{deal_id}/similar")
async def find_similar(deal_id: UUID):
    from backend.services.autonomous_services import DealRecoveryEngine
    svc = DealRecoveryEngine(); return await svc.find_similar(deal_id)

@router.get("/health/{deal_id}")
async def deal_health(deal_id: UUID):
    from backend.services.autonomous_services import OperationalHealthService
    svc = OperationalHealthService(); return await svc.evaluate(deal_id)

@router.get("/recommendations/{deal_id}")
async def get_recommendations(deal_id: UUID):
    from backend.services.autonomous_services import ActionRecommendationService
    svc = ActionRecommendationService(); r = await svc.recommend(deal_id)
    return [{"action": a.action, "expected_impact": a.expected_impact, "confidence": a.confidence, "sources": a.sources} for a in r]

@router.get("/approvals")
async def get_pending_approvals():
    from backend.services.autonomous_services import ExecutiveActionCenter
    svc = ExecutiveActionCenter(); return await svc.get_pending_approvals()

@router.post("/approvals/{item_id}/approve")
async def approve_item(item_id: UUID):
    from backend.services.autonomous_services import ExecutiveActionCenter
    svc = ExecutiveActionCenter(); r = await svc.approve(item_id)
    return {"approved": r}

@router.post("/approvals/{item_id}/reject")
async def reject_item(item_id: UUID, reason: str = ""):
    from backend.services.autonomous_services import ExecutiveActionCenter
    svc = ExecutiveActionCenter(); r = await svc.reject(item_id, reason)
    return {"rejected": r}

@router.post("/tasks/compliance")
async def compliance_tasks(score: float = 0.0, missing: list[str] = [], deal_id: str = ""):
    from backend.services.autonomous_services import TaskOrchestrator
    svc = TaskOrchestrator()
    tasks = await svc.generate_from_compliance(score, missing, UUID(deal_id) if deal_id else UUID(int=1))
    return [{"problem": t.problem, "action": t.action, "priority": t.priority} for t in tasks]

@router.post("/tasks/sla-breach")
async def sla_breach_tasks(stage: str = "", days_overdue: int = 1, deal_id: str = ""):
    from backend.services.autonomous_services import TaskOrchestrator
    svc = TaskOrchestrator()
    tasks = await svc.generate_from_sla_breach(stage, days_overdue, UUID(deal_id) if deal_id else UUID(int=1))
    return [{"problem": t.problem, "action": t.action, "priority": t.priority} for t in tasks]
