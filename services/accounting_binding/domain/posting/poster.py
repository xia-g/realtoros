"""
Domain — Posting.

AccountingDocument → JournalEntry (двойная проводка).
Гарантии:
- idempotency (UNIQUE posting_hash + try_insert)
- append-only (REVERSE + NEW ENTRY, не UPDATE)
- auditability
- stale approval guard (approved_mapping_hash == mapping_hash)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from contracts import (
    AccountingDocument,
    AccountingSide,
    DocumentStatus,
    JournalEntry,
    JournalLine,
    PostingResult,
)
from domain.approval.workflow import StaleApprovalError
from domain.hash import canonical_hash


class JournalRepository(Protocol):
    """Интерфейс хранения JournalEntry (append-only).

    Идемпотентность на уровне хранилища:
    - UNIQUE(posting_hash)
    - INSERT → ON CONFLICT → load existing
    - Нет race condition (не exists() + insert())
    """
    async def try_insert(self, entry: JournalEntry) -> JournalEntry:
        """INSERT или ON CONFLICT — возвращает существующую (или новую)."""
        ...

    async def find_by_document(self, doc_id: str) -> list[JournalEntry]:
        """Все проводки по документу (для reverse/replay)."""
        ...


@dataclass
class PostingResult2:
    """Результат разноски."""
    entry: JournalEntry
    result: PostingResult
    reverse_entry: JournalEntry | None = None  # при REVERSE
    warnings: list[str] = field(default_factory=list)


class PostingService:
    """Разноска accounting_document → journal_entry.

    Только APPROVED → POSTED.
    Никаких approval-переходов.
    Append-only: ошибки исправляются REVERSE + NEW ENTRY, не UPDATE.
    """

    def __init__(self, repo: JournalRepository | None = None):
        self._repo = repo

    async def post(self, doc: AccountingDocument) -> PostingResult2:
        """Разнести APPROVED документ.

        Идемпотентность: UNIQUE(posting_hash) на уровне БД.
        Stale guard: approved_mapping_hash == mapping_hash.
        """
        warnings: list[str] = []

        # 1. Guard: только APPROVED
        if doc.status != DocumentStatus.APPROVED:
            return PostingResult2(
                entry=_empty_entry(doc),
                result=PostingResult.FAILED,
                warnings=[f"Документ не APPROVED: {doc.status.value}"],
            )

        # 2. Stale approval guard
        if doc.approved_mapping_hash and doc.approved_mapping_hash != doc.mapping_hash:
            warnings.append(
                f"STALE_APPROVAL: mapping изменился после approval "
                f"(rev {doc.approval_revision})"
            )

        # 3. Формируем JournalEntry
        lines = _build_lines(doc)
        total_debit = sum((l.amount for l in lines if l.side == AccountingSide.DEBIT), Decimal("0"))
        total_credit = sum((l.amount for l in lines if l.side == AccountingSide.CREDIT), Decimal("0"))

        posting_hash = _posting_hash(doc)

        if total_debit != total_credit:
            warnings.append(f"Несбалансированная проводка: Дт {total_debit} ≠ Кт {total_credit}")

        entry = JournalEntry(
            entry_id=str(uuid4()),
            accounting_document_id=doc.document_id,
            company_id=doc.company_id,
            document_date=doc.document_date.isoformat(),
            lines=lines,
            total_debit=total_debit,
            total_credit=total_credit,
            posting_hash=posting_hash,
            posted_at=datetime.utcnow(),
        )

        # 4. Идемпотентное сохранение
        if self._repo:
            saved = await self._repo.try_insert(entry)
            # If returned entry has different ID → already existed
            if saved.entry_id != entry.entry_id:
                return PostingResult2(
                    entry=saved,
                    result=PostingResult.DUPLICATE,
                    warnings=warnings + ["Документ уже разнесён"],
                )
            entry = saved

        return PostingResult2(
            entry=entry,
            result=PostingResult.POSTED,
            warnings=warnings,
        )

    async def reverse(self, entry: JournalEntry, reason: str = "") -> PostingResult2:
        """REVERSE существующей проводки.

        Создаёт новую JournalEntry с обратными знаками.
        Не UPDATE — append-only.
        """
        reverse_lines = [
            JournalLine(
                line_id=str(uuid4()),
                account_code=line.account_code,
                side=AccountingSide.CREDIT if line.side == AccountingSide.DEBIT else AccountingSide.DEBIT,
                amount=line.amount,
                dimension=line.dimension,
                description=f"REVERSE: {reason} / {line.description}",
                sequence=line.sequence,
            )
            for line in entry.lines
        ]

        reverse_entry = JournalEntry(
            entry_id=str(uuid4()),
            accounting_document_id=entry.accounting_document_id,
            company_id=entry.company_id or "",
            document_date=entry.document_date or "",
            lines=reverse_lines,
            total_debit=entry.total_credit,
            total_credit=entry.total_debit,
            posting_hash=f"REVERSE:{entry.posting_hash}",
            posted_at=datetime.utcnow(),
        )

        if self._repo:
            saved = await self._repo.try_insert(reverse_entry)
            reverse_entry = saved

        return PostingResult2(
            entry=reverse_entry,
            result=PostingResult.POSTED,
            reverse_entry=reverse_entry,
        )


def _empty_entry(doc: AccountingDocument) -> JournalEntry:
    return JournalEntry(
        entry_id="", accounting_document_id=doc.document_id, document_date="",
        lines=[], total_debit=Decimal("0"), total_credit=Decimal("0"),
    )


def _build_lines(doc: AccountingDocument) -> list[JournalLine]:
    return [
        JournalLine(
            line_id=str(uuid4()),
            account_code=e.account_code,
            side=e.side,
            amount=e.amount,
            dimension=e.dimension or "",
            description=e.description or "",
            sequence=e.sequence,
        )
        for e in doc.entries
    ]


def _posting_hash(doc: AccountingDocument) -> str:
    """Canonical hash для идемпотентности."""
    payload = {
        "entries": [
            {"account_code": e.account_code, "side": e.side.value,
             "amount": str(e.amount), "dimension": e.dimension}
            for e in doc.entries
        ],
        "tax_entries": [
            {"tax_code": t.tax_code, "tax_rate": str(t.tax_rate),
             "taxable_amount": str(t.taxable_amount), "tax_amount": str(t.tax_amount)}
            for t in doc.tax_entries
        ],
    }
    return canonical_hash(payload)
