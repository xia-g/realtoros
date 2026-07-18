"""
Repository — AccountingDocument.

Работает через Mapper: Domain ↔ Record.
Нет repo.commit() — только UoW.commit().
"""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from contracts import AccountingDocument
from infrastructure.mappers.accounting_document_mapper import (
    AccountingDocumentMapper,
)
from infrastructure.models.accounting_document_record import (
    AccountingDocumentRecord,
)


class AccountingDocumentRepository:
    """Репозиторий accounting_document.

    Сохраняет доменные объекты через Mapper.
    commit() — только через Unit of Work.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._mapper = AccountingDocumentMapper()

    async def save(self, doc: AccountingDocument) -> None:
        """Сохранить (INSERT или UPDATE)."""
        record = self._mapper.domain_to_record(doc)
        await self._session.merge(record)

    async def get_by_id(self, doc_id: str) -> AccountingDocument | None:
        """Загрузить по ID."""
        result = await self._session.execute(
            select(AccountingDocumentRecord).where(
                AccountingDocumentRecord.id == doc_id
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return None
        return self._mapper.record_to_domain(record)

    async def get_by_status(
        self, status: str, limit: int = 50
    ) -> list[AccountingDocument]:
        """Найти по статусу."""
        result = await self._session.execute(
            select(AccountingDocumentRecord)
            .where(AccountingDocumentRecord.status == status)
            .limit(limit)
        )
        return [
            self._mapper.record_to_domain(r) for r in result.scalars().all()
        ]

    async def get_by_mapping_hash(
        self, mapping_hash: str
    ) -> AccountingDocument | None:
        """Найти по хешу (идетмпотентность)."""
        result = await self._session.execute(
            select(AccountingDocumentRecord).where(
                AccountingDocumentRecord.mapping_hash == mapping_hash
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return None
        return self._mapper.record_to_domain(record)
