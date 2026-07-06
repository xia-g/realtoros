"""Base service class with common CRUD operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.base import GenericRepository


class BaseService:
    """Base service with common operations delegating to repository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @property
    def repo(self) -> GenericRepository:
        raise NotImplementedError

    async def create(self, **kwargs):
        return await self.repo.create(**kwargs)

    async def get(self, id: UUID):
        return await self.repo.get(id)

    async def list(self, page=1, page_size=50, filters=None, order_by=None, descending=False):
        return await self.repo.list(
            page=page,
            page_size=page_size,
            filters=filters,
            order_by=order_by,
            descending=descending,
        )

    async def update(self, id: UUID, **kwargs):
        return await self.repo.update(id, **kwargs)

    async def delete(self, id: UUID) -> bool:
        return await self.repo.delete(id)
