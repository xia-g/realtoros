"""
Repository — JournalEntry.

INSERT → ON CONFLICT → return existing (idempotent).
Append-only: нет UPDATE.
Нет repo.commit() — только UoW.commit().
"""
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from contracts import JournalEntry, JournalLine, AccountingSide
from infrastructure.models.journal_entry_record import JournalEntryRecord


class JournalEntryRepository:
    """Репозиторий journal_entry (append-only).

    try_insert:
    - INSERT
    - ON CONFLICT (posting_hash) → load existing
    - Нет race condition
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def try_insert(self, entry: JournalEntry) -> JournalEntry:
        """INSERT или ON CONFLICT — возвращает существующую."""
        record = self._to_record(entry)

        # SQLite: INSERT OR IGNORE → select
        # PostgreSQL: INSERT ON CONFLICT DO NOTHING → RETURNING
        stmt = sqlite_insert(JournalEntryRecord).values(
            id=record.id,
            accounting_document_id=record.accounting_document_id,
            company_id=record.company_id,
            document_date=record.document_date,
            lines_json=record.lines_json,
            total_debit=record.total_debit,
            total_credit=record.total_credit,
            posting_hash=record.posting_hash,
            process_state=record.process_state,
            posted_at=record.posted_at,
            posted_by=record.posted_by,
        ).on_conflict_do_nothing()

        await self._session.execute(stmt)

        # Загружаем (существующую или новую)
        result = await self._session.execute(
            select(JournalEntryRecord).where(
                JournalEntryRecord.accounting_document_id == entry.accounting_document_id,
                JournalEntryRecord.posting_hash == entry.posting_hash,
            ).order_by(JournalEntryRecord.created_at.desc()).limit(1)
        )
        saved = result.scalar_one()
        return self._to_domain(saved)

    async def find_by_document(self, doc_id: str) -> list[JournalEntry]:
        """Все проводки по документу."""
        result = await self._session.execute(
            select(JournalEntryRecord).where(
                JournalEntryRecord.accounting_document_id == doc_id
            ).order_by(JournalEntryRecord.created_at)
        )
        return [self._to_domain(r) for r in result.scalars().all()]

    async def find_by_hash(self, posting_hash: str) -> JournalEntry | None:
        """Найти по хешу."""
        result = await self._session.execute(
            select(JournalEntryRecord).where(
                JournalEntryRecord.posting_hash == posting_hash
            )
        )
        record = result.scalar_one_or_none()
        return self._to_domain(record) if record else None

    def _to_record(self, entry: JournalEntry) -> JournalEntryRecord:
        return JournalEntryRecord(
            id=entry.entry_id or str(uuid4()),
            accounting_document_id=entry.accounting_document_id,
            company_id=entry.company_id,
            document_date=entry.document_date,
            lines_json=json.dumps(
                [l.model_dump(mode="json") for l in entry.lines],
                ensure_ascii=False, default=str,
            ),
            total_debit=entry.total_debit,
            total_credit=entry.total_credit,
            posting_hash=entry.posting_hash,
            process_state=entry.process_state,
            posted_at=entry.posted_at,
            posted_by=entry.posted_by or "",
        )

    def _to_domain(self, record: JournalEntryRecord) -> JournalEntry:
        lines_data = json.loads(record.lines_json or "[]")
        return JournalEntry(
            entry_id=record.id,
            accounting_document_id=record.accounting_document_id,
            company_id=record.company_id,
            document_date=record.document_date,
            lines=[JournalLine(**l) for l in lines_data],
            total_debit=record.total_debit,
            total_credit=record.total_credit,
            posting_hash=record.posting_hash or "",
            process_state=record.process_state,
            posted_at=record.posted_at,
            posted_by=record.posted_by or "",
        )
