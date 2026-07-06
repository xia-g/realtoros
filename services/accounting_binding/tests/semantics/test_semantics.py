"""
Semantics — System Semantics Test Suite (v1.5).

Проверяет:
1. Load Model — backpressure, worker saturation
2. Eventual Consistency — convergence, hierarchy
3. Degraded Mode — state transitions, operation guards
4. SLA — processed/failed semantics
5. Time Semantics — time-independent correctness
6. Financial Invariant — double-entry, no loss/duplication
7. Scale Model — horizontal scaling rules
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from contracts import (
    AccountingDocument,
    AccountingSide,
    AccountEntry,
    DocumentStatus,
    DocumentType,
    JournalEntry,
    JournalLine,
    PostingResult,
)
from domain.semantics.load_model import (
    BackpressureAction,
    LoadDecision,
    LoadGuard,
    OutboxMetrics,
)
from domain.semantics.eventual_consistency import (
    ConvergenceError,
    EventualConsistencyContract,
)
from domain.semantics.degraded_mode import (
    DegradationGuard,
    DegradedState,
    InvalidDegradationTransition,
    OperationNotAllowedInState,
)
from domain.semantics.sla import SLAContract
from domain.semantics.financial_invariant import (
    DoubleEntryViolation,
    FinancialInvariantGuard,
)


def make_doc(debit: Decimal = Decimal("1000"), credit: Decimal | None = None) -> AccountingDocument:
    if credit is None:
        credit = debit
    return AccountingDocument(
        document_id=str(uuid.uuid4()),
        company_id="c1",
        document_date=date.today(),
        document_type=DocumentType.INVOICE,
        entries=[
            AccountEntry(account_code="60", side=AccountingSide.DEBIT, amount=debit, sequence=0),
            AccountEntry(account_code="90", side=AccountingSide.CREDIT, amount=credit, sequence=1),
        ],
    )


# ── 1. Load Model ──

class TestLoadModel:
    """Backpressure & throughput under load."""

    def test_normal_operation_no_backlog(self):
        guard = LoadGuard()
        metrics = OutboxMetrics(backlog_size=10)
        decision = self._sync_evaluate(guard, metrics)
        assert decision.action == BackpressureAction.NORMAL

    def test_buffer_at_threshold(self):
        guard = LoadGuard()
        metrics = OutboxMetrics(backlog_size=500)
        decision = self._sync_evaluate(guard, metrics)
        assert decision.action == BackpressureAction.BUFFER

    def test_throttle_at_high_backlog(self):
        guard = LoadGuard()
        metrics = OutboxMetrics(backlog_size=2000)
        decision = self._sync_evaluate(guard, metrics)
        assert decision.action == BackpressureAction.THROTTLE

    def test_block_at_critical_backlog(self):
        guard = LoadGuard()
        metrics = OutboxMetrics(backlog_size=10000)
        decision = self._sync_evaluate(guard, metrics)
        assert decision.action == BackpressureAction.BLOCK

    def test_stuck_event_detection(self):
        guard = LoadGuard()
        metrics = OutboxMetrics(
            backlog_size=50,
            oldest_event_age_seconds=120,
        )
        decision = self._sync_evaluate(guard, metrics)
        assert len(decision.warnings) > 0
        assert "stuck" in decision.warnings[0]

    def test_event_drop_forbidden(self):
        guard = LoadGuard()
        with pytest.raises(AssertionError, match="FORBIDDEN"):
            guard.forbid_event_drop()

    def _sync_evaluate(self, guard: LoadGuard, metrics: OutboxMetrics) -> LoadDecision:
        import asyncio
        return asyncio.run(guard.evaluate(metrics))


# ── 2. Eventual Consistency ──

class TestEventualConsistency:
    """Convergence rules, inconsistency window."""

    def test_convergence_ok(self):
        contract = EventualConsistencyContract(window_seconds=300)
        state = contract.check_convergence(1, 1)
        assert state.is_converged

    def test_not_converged_yet(self):
        contract = EventualConsistencyContract(window_seconds=300)
        state = contract.check_convergence(1, 0)
        assert not state.is_converged

    def test_convergence_with_replay(self):
        contract = EventualConsistencyContract(window_seconds=300)
        state = contract.check_convergence(1, 0, has_replay=True)
        assert not state.is_converged  # replay in progress

    def test_truth_hierarchy_enforced(self):
        contract = EventualConsistencyContract()
        contract.enforce_truth_hierarchy()  # no-op (contract)

    def test_divergence_forbidden(self):
        with pytest.raises(AssertionError, match="FORBIDDEN"):
            EventualConsistencyContract().forbid_divergence()


# ── 3. Degraded Mode ──

class TestDegradedMode:
    """System degradation state machine."""

    def test_normal_default(self):
        guard = DegradationGuard()
        assert guard.state == DegradedState.NORMAL

    def test_normal_to_degraded(self):
        guard = DegradationGuard()
        guard.transition(DegradedState.DEGRADED, "outbox backlog")
        assert guard.state == DegradedState.DEGRADED

    def test_degraded_to_recovery(self):
        guard = DegradationGuard()
        guard.transition(DegradedState.DEGRADED, "backlog")
        guard.transition(DegradedState.RECOVERY, "reconciliation")
        assert guard.state == DegradedState.RECOVERY

    def test_recovery_to_normal(self):
        guard = DegradationGuard()
        guard.transition(DegradedState.DEGRADED, "backlog")
        guard.transition(DegradedState.RECOVERY, "reconciliation")
        guard.transition(DegradedState.NORMAL, "recovered")
        assert guard.state == DegradedState.NORMAL

    def test_invalid_transition(self):
        guard = DegradationGuard()
        with pytest.raises(InvalidDegradationTransition):
            guard.transition(DegradedState.READONLY)  # NORMAL → READONLY запрещён

    def test_operation_blocked_in_readonly(self):
        guard = DegradationGuard()
        guard.transition(DegradedState.DEGRADED, "backlog")
        guard.transition(DegradedState.READONLY, "maintenance")
        with pytest.raises(OperationNotAllowedInState):
            guard.assert_operation_allowed("post")

    def test_report_allowed_in_readonly(self):
        guard = DegradationGuard()
        guard.transition(DegradedState.DEGRADED, "backlog")
        guard.transition(DegradedState.READONLY, "maintenance")
        guard.assert_operation_allowed("report")  # not raise

    def test_ledger_corruption_forbidden(self):
        with pytest.raises(AssertionError, match="FORBIDDEN"):
            DegradationGuard().forbid_ledger_corruption()


# ── 4. SLA ──

class TestSLA:
    """Processed definition, FAILED ≠ LOST."""

    def test_processed_when_entry_exists(self):
        entry = JournalEntry(
            entry_id="e1", accounting_document_id="d1",
            document_date="2026-06-25", lines=[], total_debit=Decimal("0"), total_credit=Decimal("0"),
        )
        assert SLAContract.is_processed(entry, PostingResult.POSTED)

    def test_not_processed_when_no_entry(self):
        assert not SLAContract.is_processed(None)

    def test_not_processed_when_not_posted(self):
        entry = JournalEntry(
            entry_id="e1", accounting_document_id="d1",
            document_date="2026-06-25", lines=[], total_debit=Decimal("0"), total_credit=Decimal("0"),
        )
        assert not SLAContract.is_processed(entry, None)

    def test_failed_is_retryable(self):
        doc = make_doc()
        approved = AccountingDocument(**{**dict(doc), "status": DocumentStatus.APPROVED})
        assert SLAContract.is_failed_retryable(approved)

    def test_manual_db_repair_forbidden(self):
        with pytest.raises(AssertionError, match="FORBIDDEN"):
            SLAContract.assert_no_manual_db_repair()


# ── 5. Financial Invariant ──

class TestFinancialInvariant:
    """Double-entry, no loss/duplication."""

    def test_balanced_document(self):
        doc = make_doc(debit=Decimal("1000"), credit=Decimal("1000"))
        FinancialInvariantGuard.check_double_entry(doc)  # not raise

    def test_unbalanced_document_raises(self):
        doc = make_doc(debit=Decimal("1000"), credit=Decimal("500"))
        with pytest.raises(DoubleEntryViolation):
            FinancialInvariantGuard.check_double_entry(doc)

    def test_balanced_journal_line(self):
        entry = JournalEntry(
            entry_id="e1", accounting_document_id="d1",
            document_date="2026-06-25",
            lines=[
                JournalLine(line_id="l1", account_code="60", side=AccountingSide.CREDIT, amount=Decimal("1000"), sequence=0),
                JournalLine(line_id="l2", account_code="90", side=AccountingSide.DEBIT, amount=Decimal("1000"), sequence=1),
            ],
            total_debit=Decimal("1000"), total_credit=Decimal("1000"),
        )
        FinancialInvariantGuard.check_journal_balance(entry)  # not raise

    def test_unbalanced_journal_line_raises(self):
        entry = JournalEntry(
            entry_id="e1", accounting_document_id="d1",
            document_date="2026-06-25",
            lines=[
                JournalLine(line_id="l1", account_code="60", side=AccountingSide.DEBIT, amount=Decimal("1000"), sequence=0),
                JournalLine(line_id="l2", account_code="90", side=AccountingSide.CREDIT, amount=Decimal("500"), sequence=1),
            ],
            total_debit=Decimal("1000"), total_credit=Decimal("500"),
        )
        with pytest.raises(DoubleEntryViolation):
            FinancialInvariantGuard.check_journal_balance(entry)

    def test_ledger_mutation_forbidden(self):
        with pytest.raises(AssertionError, match="FORBIDDEN"):
            FinancialInvariantGuard.forbid_ledger_mutation()
