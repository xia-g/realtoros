"""
Unit of Work — транзакционная граница.

Гарантирует:
- save(document) + append(outbox) + commit() в одной транзакции
- Нет repo.commit() внутри репозиториев
- Rollback при ошибке
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.repositories.accounting_document_repo import (
    AccountingDocumentRepository,
)
from infrastructure.repositories.journal_repo import JournalEntryRepository
from infrastructure.repositories.outbox_repo import OutboxRepository


class UnitOfWork:
    """Транзакционная граница для accounting_binding.

    Использование:
        async with uow:
            uow.accounts.save(doc)
            uow.outbox.push(event)
            await uow.commit()
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self.accounts: AccountingDocumentRepository | None = None
        self.journal: JournalEntryRepository | None = None
        self.outbox: OutboxRepository | None = None

    async def __aenter__(self) -> "UnitOfWork":
        self.accounts = AccountingDocumentRepository(self._session)
        self.journal = JournalEntryRepository(self._session)
        self.outbox = OutboxRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self._session.rollback()
            return
        if self._session.is_active:
            await self._session.commit()

    async def commit(self) -> None:
        """Явный commit внутри UoW."""
        if self._session.is_active:
            await self._session.commit()

    async def rollback(self) -> None:
        """Явный rollback."""
        if self._session.is_active:
            await self._session.rollback()


async def get_uow(session: AsyncSession) -> AsyncGenerator[UnitOfWork, None]:
    """DI: UoW для FastAPI."""
    async with UnitOfWork(session) as uow:
        yield uow
