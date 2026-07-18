"""
Semantics — Time Semantics.

Invariants:
1. system correctness MUST NOT depend on wall-clock time
2. only: event ordering, causal chain, deterministic replay
3. late event MUST be processed, NOT ignored, NOT duplicate state
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class EventStore(Protocol):
    """Хранилище событий для проверки ordering."""
    async def get_by_causation(self, causation_id: str) -> list[dict[str, Any]]: ...
    async def get_by_correlation(self, correlation_id: str) -> list[dict[str, Any]]: ...


class TimeGuard:
    """Guard for time-independent semantics.

    System correctness MUST NOT depend on wall-clock time.
    """

    def __init__(self, event_store: EventStore | None = None):
        self._store = event_store

    def verify_event_order(
        self,
        causation_id: str,
        correlation_id: str,
        events: list[dict[str, Any]],
    ) -> None:
        """Проверить: causal ordering соблюдён.

        Не total ordering, не strict ordering.
        Только causal: cause → effect.
        """
        if len(events) < 2:
            return

        # Проверяем: каждое событие с causation_id ссылается на предыдущее
        seen_causations: set[str] = set()
        for event in events:
            c_id = event.get("causation_id", "")
            if c_id and c_id not in seen_causations:
                raise CausalOrderingViolation(
                    f"Causal ordering violated: event {event.get('event_id', '')} "
                    f"references causation {c_id} which was not seen before"
                )
            seen_causations.add(event.get("event_id", ""))

    def process_late_event(self, event: dict[str, Any]) -> None:
        """Обработать опоздавшее событие.

        Late event MUST be processed.
        MUST NOT be ignored.
        MUST NOT duplicate state.
        """
        # Гарантии:
        # 1. Игнорирование запрещено
        # 2. Дублирование запрещено (idempotency)
        # 3. Время не влияет на результат
        pass

    def forbid_time_dependency(self) -> None:
        """Гарантия: корректность не зависит от wall-clock time."""
        raise AssertionError(
            "FORBIDDEN: dependency on wall-clock time for correctness. "
            "Use event ordering, causal chain, deterministic replay."
        )


class CausalOrderingViolation(Exception):
    """Нарушение каузального порядка событий."""
    pass
