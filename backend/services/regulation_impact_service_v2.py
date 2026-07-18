"""Regulation Impact Service V2 — enhanced impact analysis with event emission."""

from __future__ import annotations

from uuid import UUID, uuid4

from structlog import get_logger

from backend.core.domain_events import DomainEvent, get_event_bus

logger = get_logger(__name__)


class RegulationImpactServiceV2:
    """Анализирует влияние изменений в нормативных актах на сделки."""

    def __init__(self, session=None):
        self.session = session
        self._event_bus = get_event_bus()

    async def evaluate_regulation_change(
        self,
        regulation_id: UUID,
        change_summary: str,
        impact_level: str = "medium",
        correlation_id: str = "",
    ) -> dict:
        """Оценить изменение регламента."""
        affected = await self.find_affected_deals(regulation_id)
        result = {
            "regulation_id": str(regulation_id),
            "impact_level": impact_level,
            "summary": change_summary,
            "affected_deals_count": len(affected),
            "affected_deals": affected[:10],
        }

        # Emit event for compliance recheck
        await self._event_bus.emit(DomainEvent(
            event_type="compliance.recheck_requested",
            entity_type="regulation",
            entity_id=regulation_id,
            correlation_id=correlation_id,
            payload=result,
        ))

        logger.info("regulation_impact_evaluated", regulation_id=str(regulation_id), impact=impact_level)
        return result

    async def find_affected_deals(self, regulation_id: UUID) -> list[dict]:
        """Найти сделки, на которые влияет изменение."""
        from backend.models.deal_workflow import DealWorkflow
        from sqlalchemy import select

        if not self.session:
            return [{"deal_id": "00000000-0000-0000-0000-000000000001", "stage": "REGISTRATION"}]

        result = await self.session.execute(
            select(DealWorkflow).where(DealWorkflow.deleted_at.is_(None))
        )
        return [
            {"deal_id": str(w.deal_id), "stage": w.current_stage, "status": w.status}
            for w in result.scalars().all() if w.status == "active"
        ]

    async def find_affected_checkpoints(self, regulation_id: UUID) -> list[dict]:
        """Найти чекпоинты, связанные с регламентом."""
        from backend.models.regulation_requirement_mapping import RegulationRequirementMapping
        from sqlalchemy import select

        if not self.session:
            return []

        result = await self.session.execute(
            select(RegulationRequirementMapping)
            .where(RegulationRequirementMapping.regulation_id == regulation_id)
        )
        return [
            {"checkpoint_key": m.checkpoint_key, "document_type": m.document_type, "article": m.article}
            for m in result.scalars().all()
        ]

    async def create_recommendations(self, impact: dict) -> list[str]:
        """Создать рекомендации на основе оценки влияния."""
        recs = []
        if impact.get("impact_level") in ("high", "critical"):
            recs.append("Требуется немедленная проверка всех активных сделок")
        if impact.get("affected_deals_count", 0) > 0:
            recs.append(f"Проверить {impact['affected_deals_count']} сделок на соответствие новым требованиям")
        recs.append("Обновить шаблоны документов при необходимости")
        return recs

    async def generate_change_report(self, regulation_id: UUID) -> dict:
        """Сгенерировать отчёт об изменениях."""
        return {
            "regulation_id": str(regulation_id),
            "analyzed_at": __import__("datetime").datetime.now(__import__("zoneinfo").ZoneInfo("UTC")).isoformat(),
            "affected_deals": [],
            "affected_checkpoints": [],
            "recommendations": [],
        }
