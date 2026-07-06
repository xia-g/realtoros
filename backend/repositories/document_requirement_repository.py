"""Document requirement repository."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.models.document_requirement import DocumentRequirement
from backend.repositories.generic_repository import GenericRepository


class DocumentRequirementRepository(GenericRepository[DocumentRequirement]):
    def __init__(self, session):
        super().__init__(session, DocumentRequirement)

    async def get_by_deal_type(self, deal_type: str) -> list[DocumentRequirement]:
        result = await self.session.execute(
            select(DocumentRequirement)
            .where(DocumentRequirement.deal_type == deal_type)
            .order_by(DocumentRequirement.sort_order)
        )
        return list(result.scalars().all())

    async def get_required(self, deal_type: str) -> list[DocumentRequirement]:
        result = await self.session.execute(
            select(DocumentRequirement)
            .where(
                DocumentRequirement.deal_type == deal_type,
                DocumentRequirement.is_required.is_(True),
            )
            .order_by(DocumentRequirement.sort_order)
        )
        return list(result.scalars().all())
