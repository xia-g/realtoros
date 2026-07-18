"""Regulation repository."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import and_, func, select

from backend.models.regulation import Regulation
from backend.repositories.generic_repository import GenericRepository


class RegulationRepository(GenericRepository[Regulation]):
    def __init__(self, session):
        super().__init__(session, Regulation)

    async def search(self, query: str, limit: int = 20) -> list[Regulation]:
        stmt = (
            select(Regulation)
            .where(
                and_(
                    Regulation.deleted_at.is_(None),
                    Regulation.effective_from <= func.current_date(),
                    (Regulation.effective_to.is_(None) | (Regulation.effective_to >= func.current_date())),
                    (
                        Regulation.title.ilike(f"%{query}%")
                        | Regulation.content.ilike(f"%{query}%")
                        | Regulation.tags.cast(str).ilike(f"%{query}%")
                    ),
                )
            )
            .order_by(Regulation.source.asc(), Regulation.effective_from.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_source(self, source: str) -> list[Regulation]:
        result = await self.session.execute(
            select(Regulation)
            .where(
                and_(
                    Regulation.source == source,
                    Regulation.deleted_at.is_(None),
                )
            )
            .order_by(Regulation.effective_from.desc())
        )
        return list(result.scalars().all())

    async def get_by_category(self, category: str) -> list[Regulation]:
        result = await self.session.execute(
            select(Regulation)
            .where(
                and_(
                    Regulation.category == category,
                    Regulation.deleted_at.is_(None),
                    Regulation.effective_from <= func.current_date(),
                    (Regulation.effective_to.is_(None) | (Regulation.effective_to >= func.current_date())),
                )
            )
            .order_by(Regulation.source.asc(), Regulation.effective_from.desc())
        )
        return list(result.scalars().all())
