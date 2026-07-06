"""
Domain — Reconciliation service.

Обнаруживает и исправляет расхождения между:
- accounting_document и journal_entry
- approval_state и process_state
- outbox событиями и фактическими проводками

Главный принцип: correction events, не mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Protocol

from contracts import (
    AccountingDocument,
    DocumentStatus,
    EnrichedDocument,
    JournalEntry,
    NormalizedDocument,
    ProcessingState,
)


class ReconciliationStatus(Enum):
    """Результат сверки."""
    CONSISTENT = auto()
    MISSING_JOURNAL = auto()       # APPROVED, но нет journal_entry
    MISSING_APPROVAL = auto()      # journal_entry есть, но не APPROVED
    HASH_MISMATCH = auto()         # mapping_hash не совпадает
    PROCESS_STALE = auto()         # process_state != реальность
    OUTBOX_GAP = auto()            # accounting_document есть, outbox — нет


@dataclass
class ReconciliationResult:
    """Результат сверки одного документа."""
    document_id: str
    status: ReconciliationStatus
    details: list[str] = field(default_factory=list)
    correction_events: list[str] = field(default_factory=list)


class ReconciliationRepository(Protocol):
    """Хранилище для reconciliation."""
    async def get_pending_accounting_docs(self) -> list[AccountingDocument]: ...
    async def get_journal_entries(self, doc_id: str) -> list[JournalEntry]: ...
    async def get_outbox_events(self, doc_id: str) -> list: ...
    async def save_correction_event(self, doc_id: str, event_type: str, payload: dict) -> None: ...


class DocumentReconciler:
    """Сверка состояния документа с реальностью.

    Обнаруживает:
    - документ APPROVED, но journal_entry нет → MISSING_JOURNAL
    - journal_entry есть, но статус не POSTED → MISSING_APPROVAL
    - mapping_hash изменился → HASH_MISMATCH
    - process_state != реальность → PROCESS_STALE
    - accounting_document есть, outbox нет → OUTBOX_GAP
    """

    def __init__(self, repo: ReconciliationRepository | None = None):
        self._repo = repo

    async def reconcile(self, doc: AccountingDocument) -> ReconciliationResult:
        """Проверить один документ."""
        details: list[str] = []
        events: list[str] = []

        # 1. Если APPROVED — должен быть journal_entry
        journal_entry_ids: set[str] = set()
        if self._repo:
            entries = await self._repo.get_journal_entries(doc.document_id)
            journal_entry_ids = {e.entry_id for e in entries}

        if doc.status == DocumentStatus.APPROVED and not journal_entry_ids:
            details.append("APPROVED but no journal_entry — posting failed or outbox lost")
            events.append("CORRECTION: re-dispatch posting")
            return ReconciliationResult(
                document_id=doc.document_id,
                status=ReconciliationStatus.MISSING_JOURNAL,
                details=details, correction_events=events,
            )

        # 2. Process state stale (check before MISSING_APPROVAL — stuck worker > status mismatch)
        if (doc.status == DocumentStatus.APPROVED
                and doc.process_state == ProcessingState.RUNNING):
            if journal_entry_ids:
                details.append(f"process_state RUNNING but journal_entry exists — worker hung")
            else:
                details.append("process_state stuck at RUNNING — possible hang")
            events.append("CORRECTION: set process_state to FAILED → retry")
            return ReconciliationResult(
                document_id=doc.document_id,
                status=ReconciliationStatus.PROCESS_STALE,
                details=details, correction_events=events,
            )

        # 3. Если journal_entry есть, но статус не POSTED
        if journal_entry_ids and doc.status != DocumentStatus.POSTED:
            details.append(f"journal_entry exists but status is {doc.status.value}")
            events.append("CORRECTION: set status to POSTED (journal_entry is truth)")
            return ReconciliationResult(
                document_id=doc.document_id,
                status=ReconciliationStatus.MISSING_APPROVAL,
                details=details, correction_events=events,
            )

        # 3. Stale approval guard
        if (doc.status == DocumentStatus.APPROVED
                and doc.approved_mapping_hash
                and doc.approved_mapping_hash != doc.mapping_hash):
            details.append(f"approved_mapping_hash {doc.approved_mapping_hash[:8]} ≠ mapping_hash {doc.mapping_hash[:8]}")
            events.append("CORRECTION: reject approval → re-map → re-approve")
            return ReconciliationResult(
                document_id=doc.document_id,
                status=ReconciliationStatus.HASH_MISMATCH,
                details=details, correction_events=events,
            )

        # 4. Process state stale
        if (doc.status == DocumentStatus.APPROVED
                and doc.process_state == ProcessingState.RUNNING):
            details.append("process_state stuck at RUNNING — possible hang")
            events.append("CORRECTION: set process_state to FAILED → retry")
            return ReconciliationResult(
                document_id=doc.document_id,
                status=ReconciliationStatus.PROCESS_STALE,
                details=details, correction_events=events,
            )

        # 5. Outbox gap
        if self._repo:
            outbox_events = await self._repo.get_outbox_events(doc.document_id)
            if doc.status in (DocumentStatus.APPROVED, DocumentStatus.POSTED) and not outbox_events:
                details.append("accounting_document exists but no outbox event")
                events.append("CORRECTION: re-create outbox event")
                return ReconciliationResult(
                    document_id=doc.document_id,
                    status=ReconciliationStatus.OUTBOX_GAP,
                    details=details, correction_events=events,
                )

        return ReconciliationResult(
            document_id=doc.document_id,
            status=ReconciliationStatus.CONSISTENT,
            details=["All states consistent"],
        )

    async def reconcile_all(self, docs: list[AccountingDocument]) -> list[ReconciliationResult]:
        """Сверить все документы."""
        results = []
        for doc in docs:
            result = await self.reconcile(doc)
            results.append(result)
        return results

    async def repair(self, result: ReconciliationResult) -> None:
        """Применить correction event (не mutation)."""
        if not self._repo:
            return
        for event in result.correction_events:
            await self._repo.save_correction_event(
                result.document_id,
                "reconciliation_correction",
                {"reason": result.details, "action": event},
            )
