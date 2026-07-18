"""Metrics collector for the accounting pipeline.

Simple in-memory counters for now. Can be replaced with Prometheus later.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricBucket:
    count: int = 0
    total_seconds: float = 0.0
    min_seconds: float = float("inf")
    max_seconds: float = 0.0

    def record(self, seconds: float) -> None:
        self.count += 1
        self.total_seconds += seconds
        self.min_seconds = min(self.min_seconds, seconds)
        self.max_seconds = max(self.max_seconds, seconds)

    @property
    def avg_seconds(self) -> float:
        return self.total_seconds / self.count if self.count else 0.0


class MetricsCollector:
    """Thread-safe metrics storage for accounting pipeline."""

    def __init__(self):
        self._timers: dict[str, dict[str, MetricBucket]] = defaultdict(lambda: defaultdict(MetricBucket))
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}

    def record(self, name: str, seconds: float, tags: dict[str, str] | None = None) -> None:
        """Record a timer metric with optional tags."""
        key = tags.get("stage", "_total") if tags else "_total"
        self._timers[name][key].record(seconds)

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter."""
        self._counters[name] += value

    def gauge(self, name: str, value: float) -> None:
        """Set a gauge value."""
        self._gauges[name] = value

    def snapshot(self) -> dict[str, Any]:
        """Return all metrics as a dict."""
        timers = {}
        for name, buckets in self._timers.items():
            timers[name] = {
                tag: {
                    "count": b.count,
                    "avg": round(b.avg_seconds, 4),
                    "min": round(b.min_seconds, 4) if b.min_seconds != float("inf") else 0,
                    "max": round(b.max_seconds, 4),
                    "total": round(b.total_seconds, 4),
                }
                for tag, b in buckets.items()
            }
        return {
            "timers": timers,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

    def reset(self) -> None:
        self._timers.clear()
        self._counters.clear()
        self._gauges.clear()


# Global singleton
metrics = MetricsCollector()
