"""
Semantics — Financial Consistency Guarantee.

Core invariants:
1. no transaction is lost
2. no transaction is duplicated in ledger
3. every posting MUST balance: debit == credit
4. system rejects imbalance automatically

Under ANY condition:
    failure, delay, duplication, crash, replay
    ledger correctness MUST hold
"""
from __future__ import annotations

from decimal import Decimal

from contracts import (
    AccountingDocument,
    AccountingSide,
    JournalEntry,
    JournalLine,
)


class DoubleEntryViolation(ValueError):
    """Нарушение double-entry: debit ≠ credit."""
    pass


class DuplicatePostingError(ValueError):
    """Попытка дублирования posting (должна быть перехвачена idempotency)."""
    pass


class FinancialInvariantGuard:
    """Guard for financial consistency invariants."""

    @staticmethod
    def check_double_entry(doc: AccountingDocument) -> None:
        """Проверить: debit == credit.

        Система автоматически отклоняет несбалансированные проводки.
        """
        debit = sum(
            e.amount for e in doc.entries
            if e.side == AccountingSide.DEBIT
        )
        credit = sum(
            e.amount for e in doc.entries
            if e.side == AccountingSide.CREDIT
        )

        if debit != credit:
            raise DoubleEntryViolation(
                f"Double-entry violation: debit {debit} != credit {credit}. "
                f"Document {doc.document_id} rejected."
            )

    @staticmethod
    def check_journal_balance(entry: JournalEntry) -> None:
        """Проверить баланс journal_entry."""
        debit = sum(
            l.amount for l in entry.lines
            if l.side == AccountingSide.DEBIT
        )
        credit = sum(
            l.amount for l in entry.lines
            if l.side == AccountingSide.CREDIT
        )

        if debit != credit:
            raise DoubleEntryViolation(
                f"Journal entry unbalanced: debit {debit} != credit {credit}. "
                f"Entry {entry.entry_id} rejected."
            )

    @staticmethod
    def verify_no_duplicate(
        existing: JournalEntry | None,
        attempted: JournalEntry,
    ) -> None:
        """Проверить: нет дублирования в ledger.

        Idempotency разрешена (DUPLICATE статус).
        Настоящее дублирование (разные hash, одинаковые данные) запрещено.
        """
        if existing and existing.posting_hash != attempted.posting_hash:
            raise DuplicatePostingError(
                f"Duplicate posting detected: entry {attempted.entry_id} "
                f"has different hash than existing {existing.entry_id} "
                f"but targets same document."
            )

    @staticmethod
    def forbid_ledger_mutation() -> None:
        """Гарантия: immutable ledger."""
        raise AssertionError(
            "FORBIDDEN: ledger mutation. "
            "Journal entries are append-only. "
            "Use REVERSE + NEW entry, not UPDATE."
        )
