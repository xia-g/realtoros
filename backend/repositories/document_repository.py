from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.models.document import Document
from backend.repositories.base import GenericRepository


class DocumentRepository(GenericRepository[Document]):
    def __init__(self, session):
        super().__init__(session, Document)

    async def find_by_hash(self, file_hash: str) -> Document | None:
        stmt = select(Document).where(Document.file_hash == file_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_client(self, client_id: UUID) -> list[Document]:
        stmt = select(Document).where(Document.client_id == client_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_property(self, property_id: UUID) -> list[Document]:
        stmt = select(Document).where(Document.property_id == property_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_deal(self, deal_id: UUID) -> list[Document]:
        stmt = select(Document).where(Document.deal_id == deal_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
