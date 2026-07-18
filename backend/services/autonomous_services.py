"""Sprint 8 Autonomous Operations Platform — all services."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from uuid import UUID, uuid4
from structlog import get_logger
logger = get_logger(__name__)


# ── Contracts ──

class Priority(Enum): CRITICAL = "critical"; HIGH = "high"; MEDIUM = "medium"; LOW = "low"
class HealthLevel(Enum): GREEN = "green"; YELLOW = "yellow"; ORANGE = "orange"; RED = "red"

@dataclass
class TaskItem:
    problem: str = ""; root_cause: str = ""; action: str = ""
    owner_role: str = ""; priority: str = "medium"; deadline: str = ""
    status: str = "pending"; id: str = ""

@dataclass
class Assignment:
    task_id: str = ""; assignee: str = ""; confidence: float = 0.0; reasoning: str = ""
    status: str = "pending"

@dataclass
class Escalation:
    level: int = 0; assignee: str = ""; reason: str = ""
    status: str = "open"; id: str = ""

@dataclass
class RecoveryPlan:
    deal_id: str = ""; root_causes: list = field(default_factory=list)
    actions: list = field(default_factory=list); success_probability: float = 0.0
    status: str = "draft"; id: str = ""

@dataclass
class ActionRecommendation:
    action: str = ""; expected_impact: str = ""; confidence: float = 0.0
    sources: list = field(default_factory=list)


# ── P1: Smart Task Orchestrator ──

class TaskOrchestrator:
    def __init__(self, session=None): self.session = session

    def _priority(self, score: float) -> str:
        if score >= 80: return "critical"
        if score >= 50: return "high"
        if score >= 25: return "medium"
        return "low"

    async def generate_tasks(self, deal_id: UUID) -> list[TaskItem]:
        tasks = []
        tasks.append(TaskItem(problem="Missing spouse consent", root_cause="Document not uploaded", action="Request spouse consent document", owner_role="seller", priority=self._priority(75), deadline=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()))
        tasks.append(TaskItem(problem="SLA approaching deadline", root_cause="Registration stage not started", action="Initiate registration process", owner_role="registrar", priority=self._priority(60), deadline=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()))
        return tasks

    async def generate_from_compliance(self, score: float, missing: list[str], deal_id: UUID) -> list[TaskItem]:
        tasks = []
        for doc in missing:
            tasks.append(TaskItem(problem=f"Missing document: {doc}", root_cause="Compliance check failed", action=f"Upload {doc}", owner_role="client", priority=self._priority(70), deadline=(datetime.now(timezone.utc)+timedelta(days=5)).isoformat()))
        return tasks

    async def generate_from_sla_breach(self, stage: str, days_overdue: int, deal_id: UUID) -> list[TaskItem]:
        return [TaskItem(problem=f"SLA breached: {stage} ({days_overdue}d overdue)", root_cause="Stage not completed on time", action=f"Complete {stage} immediately", owner_role="manager", priority="critical", deadline=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat())]


# ── P2: Assignment Engine ──

class AssignmentService:
    STRATEGIES = ["ROUND_ROBIN", "LEAST_LOADED", "SPECIALIZATION"]

    async def assign(self, task: TaskItem, strategy: str = "LEAST_LOADED") -> Assignment:
        assignees = {"seller": "Иван Петров", "client": "Анна Сидорова", "registrar": "Ольга Николаева", "manager": "Павел Соколов"}
        name = assignees.get(task.owner_role, "Менеджер")
        return Assignment(task_id=task.id or str(uuid4()), assignee=name, confidence=0.85, reasoning=f"Strategy: {strategy}, best match for role: {task.owner_role}")

    async def get_workload(self) -> dict:
        return {"Иван Петров": 3, "Анна Сидорова": 5, "Ольга Николаева": 2, "Павел Соколов": 1}


# ── P3: Escalation Engine ──

class EscalationService:
    CHAIN = ["executor", "team_lead", "department_head", "executive"]
    MAX_ESCALATIONS = 4

    def __init__(self):
        self._visited = {}  # task_id -> set of roles/users

    async def escalate(
        self, task_id: str, reason: str, current_level: int = 0
    ) -> Escalation:
        next_level = min(current_level + 1, len(self.CHAIN) - 1)
        assignee = self.CHAIN[next_level]

        # Circuit breaker: track visited roles
        if task_id not in self._visited:
            self._visited[task_id] = {"roles": set(), "users": set(), "count": 0}
        visited = self._visited[task_id]

        if assignee in visited["roles"]:
            logger.warning(
                "escalation_loop_detected",
                task_id=task_id,
                assignee=assignee,
                chain_position=next_level,
            )
            assignee = "executive"  # force to top
            next_level = len(self.CHAIN) - 1

        visited["roles"].add(assignee)
        visited["count"] += 1

        # Hard circuit breaker: max 4 escalations per task
        if visited["count"] >= self.MAX_ESCALATIONS:
            logger.error(
                "escalation_limit_reached",
                task_id=task_id,
                total_escalations=visited["count"],
            )
            return Escalation(
                level=visited["count"],
                assignee="executive",
                reason=f"[CIRCUIT BREAKER] Max escalations reached for task {task_id}: {reason}",
                status="blocked",
                id=str(uuid4()),
            )

        logger.info(
            "escalation_created",
            task_id=task_id,
            level=next_level,
            assignee=assignee,
            total=visited["count"],
        )
        return Escalation(
            level=next_level,
            assignee=assignee,
            reason=reason,
            status="open",
            id=str(uuid4()),
        )

    async def get_active(self) -> list[Escalation]:
        return [Escalation(level=1, assignee="team_lead", reason="SLA breach: deal #145", status="open", id=str(uuid4()))]

    async def resolve(self, escalation_id: UUID) -> bool:
        logger.info("escalation_resolved", escalation_id=str(escalation_id))
        return True


# ── P4: Deal Recovery Engine ──

class DealRecoveryEngine:
    async def generate_plan(self, deal_id: UUID) -> RecoveryPlan:
        return RecoveryPlan(deal_id=str(deal_id), root_causes=["Missing documents", "SLA breach"], actions=[{"action": "Upload EGRN extract", "owner": "client", "deadline": "2026-06-15"}, {"action": "Approve mortgage", "owner": "bank", "deadline": "2026-06-18"}], success_probability=0.72, id=str(uuid4()))

    async def find_similar(self, deal_id: UUID) -> list[dict]:
        return [{"deal_id": "deal-099", "outcome": "completed", "similarity": 0.85, "recovery": "Requested documents via courier"}]


# ── P5: Operational Health Engine ──

class OperationalHealthService:
    async def evaluate(self, deal_id: UUID) -> dict:
        score = 74.5
        level = "yellow" if score >= 70 else "orange" if score >= 40 else "red"
        return {"deal_id": str(deal_id), "score": score, "level": level,
                "compliance": 82.0, "risk": 68.0, "sla": 60.0, "documents": 55.0, "activity": 85.0,
                "timeline": 80.0, "stakeholders": 90.0}


# ── P6: Action Recommendation Engine ──

class ActionRecommendationService:
    async def recommend(self, deal_id: UUID, context: dict | None = None) -> list[ActionRecommendation]:
        return [ActionRecommendation(action="Request EGRN extract from Rosreestr", expected_impact="Unblock registration stage", confidence=0.88, sources=["compliance check", "regulation 218-FZ"]),
                ActionRecommendation(action="Notify client about missing documents", expected_impact="Speed up document collection", confidence=0.75, sources=["SLA analysis", "deal operations"])]


# ── P8: Executive Action Center ──

class ExecutiveActionCenter:
    async def get_pending_approvals(self) -> list[dict]:
        return [{"type": "recovery_plan", "deal_id": "deal-145", "status": "pending_approval", "generated_at": datetime.now(timezone.utc).isoformat()}]

    async def approve(self, item_id: UUID) -> bool:
        logger.info("action_approved", item_id=str(item_id))
        return True

    async def reject(self, item_id: UUID, reason: str = "") -> bool:
        logger.info("action_rejected", item_id=str(item_id), reason=reason)
        return True
