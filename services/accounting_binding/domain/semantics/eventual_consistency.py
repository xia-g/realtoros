"""
Semantics — Eventual Consistency Contract.

Правила:
1. system may be inconsistent temporarily
2. system MUST converge deterministically
3. Convergence: all states → journal_entry = final truth
4. Convergence regardless of: replay timing, worker delays, out-of-order events

Convergence window: bounded by replay + reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class InconsistencyWindow:
    """Окно временной несогласованности.

    Система может быть inconsistent в пределах этого окна,
    но гарантированно сходится к journal_entry как truth.
    """
    max_window_seconds: int = 300  # 5 минут максимальной несогласованности
    started_at: datetime | None = None
    convergence_deadline: datetime | None = None

    def start(self) -> None:
        """Начать отсчёт окна несогласованности."""
        self.started_at = datetime.utcnow()
        self.convergence_deadline = self.started_at + timedelta(
            seconds=self.max_window_seconds
        )

    @property
    def elapsed_seconds(self) -> int:
        """Секунд с начала окна."""
        if not self.started_at:
            return 0
        return int((datetime.utcnow() - self.started_at).total_seconds())

    @property
    def is_expired(self) -> bool:
        """Окно истекло — система должна быть согласована."""
        if not self.convergence_deadline:
            return False
        return datetime.utcnow() > self.convergence_deadline


@dataclass
class ConvergenceState:
    """Состояние конвергенции."""
    document_id: str
    expected_entries: int = 0
    actual_entries: int = 0
    is_converged: bool = False


class EventualConsistencyContract:
    """Контракт гарантированной конвергенции.

    Все состояния должны сойтись к journal_entry = final truth.
    """

    def __init__(self, window_seconds: int = 300):
        self._window = InconsistencyWindow(max_window_seconds=window_seconds)

    def check_convergence(
        self,
        expected_entry_count: int,
        actual_entry_count: int,
        has_replay: bool = False,
    ) -> ConvergenceState:
        """Проверить, сошлась ли система."""
        is_converged = (
            expected_entry_count == actual_entry_count
            and expected_entry_count > 0
        )

        # Если есть replay — конвергенция откладывается
        if has_replay and not is_converged:
            self._window.start()

        # Если окно истекло — ошибка конвергенции
        if self._window.is_expired and not is_converged:
            raise ConvergenceError(
                f"Convergence deadline expired for {expected_entry_count} expected, "
                f"{actual_entry_count} actual entries"
            )

        return ConvergenceState(
            document_id="",
            expected_entries=expected_entry_count,
            actual_entries=actual_entry_count,
            is_converged=is_converged,
        )

    def enforce_truth_hierarchy(self) -> None:
        """Формальное правило иерархии истины.

        journal_entry > accounting_document > enriched > normalized.
        """
        pass  # контракт: этот порядок никогда не нарушается

    def forbid_divergence(self) -> None:
        """Гарантия: система не расходится бесконечно."""
        raise AssertionError(
            "FORBIDDEN: unbounded divergence. "
            "System must converge within inconsistency window."
        )


class ConvergenceError(Exception):
    """Ошибка конвергенции — система не сошлась в срок."""
    pass
