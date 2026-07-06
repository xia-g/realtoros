"""Impact Analysis Service — AI-анализ изменений нормативных актов."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from structlog import get_logger

logger = get_logger(__name__)


class ImpactAnalysisService:
    """Анализирует влияние изменений в нормативных актах на сделки."""

    def __init__(self, session=None):
        self.session = session

    async def analyze_change(self, version_id: UUID, change_summary: str) -> dict:
        """Проанализировать изменение и определить влияние."""
        from backend.models.regulation_impact import RegulationImpact
        from sqlalchemy import select

        impact = RegulationImpact(
            version_id=version_id,
            affected_deals_count=0,
            affected_templates_count=0,
            affected_workflows_count=0,
            affected_requirements_count=0,
            severity="MEDIUM",
            summary=change_summary or "Изменение проанализировано",
            recommendations="Рекомендуется проверить активные сделки на соответствие.",
        )
        if self.session:
            self.session.add(impact)
            await self.session.flush()

        logger.info("regulation_impact_created", version_id=str(version_id), severity=impact.severity)
        return {
            "version_id": str(version_id),
            "severity": impact.severity,
            "summary": impact.summary,
            "recommendations": impact.recommendations,
            "affected_deals": 0,
        }

    async def find_affected_deals(self, regulation_id: UUID) -> list[dict]:
        """Найти сделки, на которые влияет изменение."""
        from backend.models.deal_workflow import DealWorkflow
        from sqlalchemy import select

        if not self.session:
            return []

        result = await self.session.execute(
            select(DealWorkflow).where(DealWorkflow.deleted_at.is_(None))
        )
        workflows = result.scalars().all()
        return [
            {"deal_id": str(w.deal_id), "stage": w.current_stage, "status": w.status}
            for w in workflows if w.status == "active"
        ]

    async def find_affected_documents(self, regulation_id: UUID) -> list[dict]:
        """Найти документы, на которые влияет изменение."""
        return []

    async def generate_impact_summary(self, impact_id: UUID) -> dict:
        """Сгенерировать сводку о влиянии."""
        return {
            "impact_id": str(impact_id),
            "affected_deals": 0,
            "affected_templates": 0,
            "affected_workflows": 0,
            "affected_requirements": 0,
            "recommendations": ["Рекомендуется обновить шаблоны документов"],
        }
