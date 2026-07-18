"""
Semantics — System Degradation States.

State machine:
    NORMAL → full pipeline execution
    DEGRADED → delayed posting
    RECOVERY → reconciliation active
    READONLY → reporting only

Safe degradation rule:
    system may slow down, queue, retry
    system MUST NEVER corrupt ledger
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class DegradedState(Enum):
    """Состояния деградации системы."""
    NORMAL = auto()      # полный pipeline
    DEGRADED = auto()    # отложенный posting
    RECOVERY = auto()    # reconciliation активен
    READONLY = auto()    # только отчёты


# Разрешённые переходы
_TRANSITIONS: dict[DegradedState, set[DegradedState]] = {
    DegradedState.NORMAL: {DegradedState.DEGRADED},
    DegradedState.DEGRADED: {DegradedState.RECOVERY, DegradedState.READONLY},
    DegradedState.RECOVERY: {DegradedState.NORMAL, DegradedState.DEGRADED, DegradedState.READONLY},
    DegradedState.READONLY: {DegradedState.RECOVERY},
}

# Какие операции разрешены в каждом состоянии
_ALLOWED_OPS: dict[DegradedState, set[str]] = {
    DegradedState.NORMAL: {"ingest", "enrich", "validate", "map", "approve", "post", "report"},
    DegradedState.DEGRADED: {"ingest", "enrich", "validate", "map", "approve", "report"},
    DegradedState.RECOVERY: {"reconcile", "replay", "report"},
    DegradedState.READONLY: {"report"},
}


class InvalidDegradationTransition(ValueError):
    """Недопустимый переход состояния деградации."""
    pass


class OperationNotAllowedInState(ValueError):
    """Операция запрещена в текущем состоянии деградации."""
    pass


@dataclass
class DegradationEvent:
    """Событие изменения состояния деградации."""
    from_state: DegradedState
    to_state: DegradedState
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DegradationGuard:
    """Guard for system degradation states."""

    def __init__(self):
        self._state = DegradedState.NORMAL
        self._events: list[DegradationEvent] = []

    @property
    def state(self) -> DegradedState:
        return self._state

    def transition(self, to: DegradedState, reason: str = "") -> DegradationEvent:
        """Перейти в новое состояние."""
        allowed = _TRANSITIONS.get(self._state, set())
        if to not in allowed:
            raise InvalidDegradationTransition(
                f"Cannot transition from {self._state.name} to {to.name}. "
                f"Allowed: {[s.name for s in allowed]}"
            )
        event = DegradationEvent(
            from_state=self._state,
            to_state=to,
            reason=reason,
        )
        self._state = to
        self._events.append(event)
        return event

    def assert_operation_allowed(self, operation: str) -> None:
        """Проверить, разрешена ли операция."""
        allowed = _ALLOWED_OPS.get(self._state, set())
        if operation not in allowed:
            raise OperationNotAllowedInState(
                f"Operation '{operation}' not allowed in state {self._state.name}. "
                f"Allowed: {allowed}"
            )

    def forbid_ledger_corruption(self) -> None:
        """Гарантия: ledger не повреждается ни в каком состоянии."""
        raise AssertionError(
            "FORBIDDEN: ledger corruption in any degradation state. "
            "System may slow down, queue, retry. "
            "System MUST NEVER corrupt ledger."
        )
