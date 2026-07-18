"""Deal checkpoint repository."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, func, select, update

from backend.models.deal_checkpoint import DealCheckpoint
from backend.repositories.generic_repository import GenericRepository


class DealCheckpointRepository(GenericRepository[DealCheckpoint]):
    def __init__(self, session):
        super().__init__(session, DealCheckpoint)

    async def get_by_deal(self, deal_id: UUID) -> list[DealCheckpoint]:
        result = await self.session.execute(
            select(DealCheckpoint)
            .where(DealCheckpoint.deal_id == deal_id, DealCheckpoint.deleted_at.is_(None))
            .order_by(DealCheckpoint.sort_order)
        )
        return list(result.scalars().all())

    async def get_by_deal_and_stage(self, deal_id: UUID, stage: str) -> list[DealCheckpoint]:
        result = await self.session.execute(
            select(DealCheckpoint)
            .where(
                DealCheckpoint.deal_id == deal_id,
                DealCheckpoint.stage == stage,
                DealCheckpoint.deleted_at.is_(None),
            )
            .order_by(DealCheckpoint.sort_order)
        )
        return list(result.scalars().all())

    async def complete_checkpoint(self, checkpoint_id: UUID, user_id: UUID) -> DealCheckpoint | None:
        result = await self.session.execute(
            update(DealCheckpoint)
            .where(DealCheckpoint.id == checkpoint_id, DealCheckpoint.deleted_at.is_(None))
            .values(is_completed=True, completed_by=user_id)
            .returning(DealCheckpoint)
        )
        return result.scalar_one_or_none()

    async def get_completion_stats(self, deal_id: UUID) -> dict:
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.sum(case((DealCheckpoint.is_completed, 1), else_=0)).label("completed"),
            )
            .where(DealCheckpoint.deal_id == deal_id, DealCheckpoint.deleted_at.is_(None))
        )
        row = result.one()
        return {"total": row.total, "completed": row.completed}
