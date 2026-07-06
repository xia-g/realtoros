"""
Semantics — Load Model (backpressure & throughput).

Invariants:
1. if outbox_backlog increases → system degrades safely, NOT lose events
2. workers > load → safe idle
3. workers < load → backlog grows, system still correct
4. Correctness ≠ latency

FORBIDDEN:
- dropping events
- skipping journal_entry
- silent loss
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol


class BackpressureAction(Enum):
    """Действие при повышенной нагрузке."""
    NORMAL = auto()             # штатный режим
    BUFFER = auto()             # буферизация (отложенный posting)
    THROTTLE = auto()           # ограничение скорости приёма
    BACKOFF = auto()            # exponential backoff для worker
    BLOCK = auto()              # блокировка приёма новых документов


@dataclass
class OutboxMetrics:
    """Метрики outbox для принятия решений."""
    backlog_size: int = 0
    oldest_event_age_seconds: int = 0
    worker_count: int = 0
    worker_queue_depth: int = 0
    posting_rate_per_minute: float = 0.0
    failure_rate_per_minute: float = 0.0


class OutboxStore(Protocol):
    """Хранилище outbox для мониторинга нагрузки."""
    async def get_metrics(self) -> OutboxMetrics: ...


class WorkerPool(Protocol):
    """Пул воркеров для масштабирования."""
    async def scale_up(self, count: int) -> None: ...
    async def scale_down(self, count: int) -> None: ...


@dataclass
class LoadDecision:
    """Решение по нагрузке."""
    action: BackpressureAction = BackpressureAction.NORMAL
    reason: str = ""
    suggested_workers: int = 0
    warnings: list[str] = field(default_factory=list)


class LoadGuard:
    """Guard for load-based backpressure.

    NORMAL → BUFFER → THROTTLE → BACKOFF → BLOCK
    """

    # Пороги (можно менять без кода)
    BACKLOG_WARN = 100        # предупреждение
    BACKLOG_BUFFER = 500      # начать буферизацию
    BACKLOG_THROTTLE = 2000   # ограничить приём
    BACKLOG_BACKOFF = 5000    # exponential backoff
    BACKLOG_BLOCK = 10000     # блокировка

    # Пороги по времени зависания
    STUCK_WARN_SECONDS = 60
    STUCK_CRITICAL_SECONDS = 300

    def __init__(
        self,
        outbox_store: OutboxStore | None = None,
        worker_pool: WorkerPool | None = None,
    ):
        self._outbox = outbox_store
        self._pool = worker_pool

    async def evaluate(self, metrics: OutboxMetrics | None = None) -> LoadDecision:
        """Оценить нагрузку и вернуть решение."""
        if not metrics and self._outbox:
            metrics = await self._outbox.get_metrics()
        if not metrics:
            return LoadDecision(action=BackpressureAction.NORMAL)

        warnings: list[str] = []
        action = BackpressureAction.NORMAL
        reason = "normal operation"

        # 1. Проверка backlog
        if metrics.backlog_size >= self.BACKLOG_BLOCK:
            action = BackpressureAction.BLOCK
            reason = f"backlog {metrics.backlog_size} >= BLOCK threshold"
            warnings.append(reason)
        elif metrics.backlog_size >= self.BACKLOG_BACKOFF:
            action = BackpressureAction.BACKOFF
            reason = f"backlog {metrics.backlog_size} >= BACKOFF threshold"
        elif metrics.backlog_size >= self.BACKLOG_THROTTLE:
            action = BackpressureAction.THROTTLE
            reason = f"backlog {metrics.backlog_size} >= THROTTLE threshold"
        elif metrics.backlog_size >= self.BACKLOG_BUFFER:
            action = BackpressureAction.BUFFER
            reason = f"backlog {metrics.backlog_size} >= BUFFER threshold"
        elif metrics.backlog_size >= self.BACKLOG_WARN:
            warnings.append(f"backlog growing: {metrics.backlog_size}")

        # 2. Проверка stuck событий
        if metrics.oldest_event_age_seconds > self.STUCK_CRITICAL_SECONDS:
            warnings.append(
                f"event stuck {metrics.oldest_event_age_seconds}s — critical"
            )
        elif metrics.oldest_event_age_seconds > self.STUCK_WARN_SECONDS:
            warnings.append(
                f"event stuck {metrics.oldest_event_age_seconds}s — warning"
            )

        # 3. Failure rate
        if metrics.failure_rate_per_minute > 10 and metrics.posting_rate_per_minute > 0:
            failure_pct = metrics.failure_rate_per_minute / metrics.posting_rate_per_minute * 100
            if failure_pct > 20:
                warnings.append(f"high failure rate: {failure_pct:.0f}%")

        # 4. Worker scaling
        suggested = metrics.worker_count
        if action in (BackpressureAction.BUFFER, BackpressureAction.THROTTLE):
            suggested = max(metrics.worker_count, int(metrics.backlog_size / 100))
        if suggested > metrics.worker_count and self._pool:
            await self._pool.scale_up(suggested - metrics.worker_count)

        return LoadDecision(
            action=action,
            reason=reason,
            suggested_workers=suggested,
            warnings=warnings,
        )

    def forbid_event_drop(self):
        """Гарантия: события не теряются.

        Это не runtime check — это формальный контракт.
        Нарушение = баг архитектуры.
        """
        raise AssertionError(
            "FORBIDDEN: dropping events under load. "
            "Use queue buffering, not discard."
        )
