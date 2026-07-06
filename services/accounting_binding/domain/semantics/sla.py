"""
Semantics — SLA Contract.

Definition of "processed":
    journal_entry EXISTS AND is idempotent-confirmed

NOT processed when:
    approval happens
    mapping happens
    validation passes

Failure semantics:
    FAILED ≠ LOST
    FAILED = RETRYABLE STATE
"""
from __future__ import annotations

from contracts import (
    AccountingDocument,
    DocumentStatus,
    JournalEntry,
    PostingResult,
    ProcessingState,
)


class SLAContract:
    """SLA контракт — формальные определения."""

    @staticmethod
    def is_processed(entry: JournalEntry | None, result: PostingResult | None = None) -> bool:
        """Документ считается processed только если journal_entry существует и idempotent-confirmed."""
        if entry is None:
            return False
        if not entry.entry_id:
            return False
        if result is None:
            return False
        if result not in (PostingResult.POSTED, PostingResult.DUPLICATE):
            return False
        return True

    @staticmethod
    def is_failed_retryable(doc: AccountingDocument) -> bool:
        """FAILED ≠ LOST. FAILED = RETRYABLE STATE."""
        return (
            doc.process_state == ProcessingState.FAILED
            or doc.status == DocumentStatus.APPROVED
        )

    @staticmethod
    def assert_failed_not_lost(doc: AccountingDocument) -> None:
        """Гарантия: FAILED ≠ LOST."""
        if not SLAContract.is_failed_retryable(doc):
            raise AssertionError(
                "FAILED state is not retryable — document cannot be recovered. "
                "FAILED must always be a retryable state."
            )

    @staticmethod
    def assert_no_manual_db_repair() -> None:
        """Гарантия: никогда не требуется ручное исправление БД."""
        raise AssertionError(
            "Manual DB repair is FORBIDDEN. "
            "Use replay, reconciliation, or correction events."
        )
