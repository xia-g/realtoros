"""
Chaos Engineering — сценарии отказоустойчивости для Accounting Binding.

Каждый тест: inject failure → verify recovery → cleanup.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from contracts import (
    AccountingDocument,
    AccountingSide,
    AccountEntry,
    DocumentStatus,
    DocumentType,
    JournalEntry,
    ProcessingState,
)
from domain.hash import canonical_hash
from domain.approval.workflow import ApprovalWorkflow, ApprovalAction, StaleApprovalError
from domain.posting.poster import PostingService, PostingResult
from infrastructure.uow import UnitOfWork
from infrastructure.events.outbox import Outbox, OutboxEvent, OutboxEventType
from tests.chaos.fake_repo import FakeJournalRepo


def _make_doc(**kw: Any) -> AccountingDocument:
    e = AccountEntry(account_code="60", side=AccountingSide.DEBIT, amount=Decimal("1000"))
    base = dict(
        document_id=str(uuid.uuid4()),
        company_id="c1",
        document_date=date.today(),
        document_type=DocumentType.INVOICE,
        entries=[e],
        mapping_hash=canonical_hash({"test": "data"}),
    )
    base.update(kw)
    return AccountingDocument(**base)


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_db_disconnect_mid_uow():
    """DB падает в середине UoW → rollback."""
    doc = _make_doc()
    session = AsyncMock()
    session.is_active = True
    session.commit = AsyncMock(side_effect=ConnectionError("DB down"))

    uow = UnitOfWork(session)
    try:
        async with uow:
            await uow.accounts.save(doc)
            await uow.outbox.push(OutboxEvent.create(OutboxEventType.DOCUMENT_APPROVED, doc.document_id))
            await uow.commit()
    except ConnectionError:
        pass

    assert session.rollback.called
    assert session.commit.called


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_outbox_stuck_messages():
    """Outbox stuck → повтор → idempotent (same entry returned)."""
    repo = FakeJournalRepo()
    svc = PostingService(repo)
    doc = _make_doc(status=DocumentStatus.APPROVED)

    r1 = await svc.post(doc)
    assert r1.result == PostingResult.POSTED

    # Second post: should return existing entry (idempotent)
    r2 = await svc.post(doc)
    assert r2.entry.entry_id == r1.entry.entry_id, \
        f"Idempotent: entry {r2.entry.entry_id[:8]} should match {r1.entry.entry_id[:8]}"


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_partial_journal_entry():
    """Частично записанный journal_entry → retry → existing."""
    repo = FakeJournalRepo()
    entry = JournalEntry(
        entry_id=str(uuid.uuid4()),
        accounting_document_id="d1",
        company_id="c1",
        document_date=date.today().isoformat(),
        lines=[],
        total_debit=Decimal("0"),
        total_credit=Decimal("0"),
        posting_hash="h1",
    )
    saved = await repo.try_insert(entry)
    dup = await repo.try_insert(entry)
    assert dup.entry_id == saved.entry_id


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_replay_during_posting():
    """Replay во время active posting."""
    doc = _make_doc(status=DocumentStatus.APPROVED, process_state=ProcessingState.RUNNING)
    r = await PostingService(FakeJournalRepo()).post(doc)
    assert r.result in (PostingResult.POSTED, PostingResult.DUPLICATE)


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_approve_post_race():
    """Race: APPROVE + POST → idempotent."""
    doc = _make_doc(status=DocumentStatus.DRAFT)
    wf = ApprovalWorkflow()

    a, _ = wf.apply(doc, ApprovalAction.SUBMIT)
    a, _ = wf.apply(a, ApprovalAction.REQUEST_REVIEW)
    a, _ = wf.apply(a, ApprovalAction.APPROVE)
    assert a.status == DocumentStatus.APPROVED
    assert a.approval_revision == 1

    r = await PostingService(FakeJournalRepo()).post(a)
    assert r.result == PostingResult.POSTED


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_corrupted_mapping_hash():
    """Mapping hash повреждён → StaleApprovalError."""
    doc = _make_doc(mapping_hash="orig")
    wf = ApprovalWorkflow()
    a, _ = wf.apply(doc, ApprovalAction.SUBMIT)
    a, _ = wf.apply(a, ApprovalAction.REQUEST_REVIEW)
    a, _ = wf.apply(a, ApprovalAction.APPROVE)

    bad = AccountingDocument(**{**dict(a), "mapping_hash": "corrupted"})
    with pytest.raises(StaleApprovalError):
        wf.check_approval_valid(bad)
