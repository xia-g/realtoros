"""
Observability — Prometheus Metrics.

Минимальный набор:
- pipeline_duration_seconds
- validation_failures_total
- approval_queue_size
- posting_duration_seconds
- outbox_backlog
- replay_total

Prometheus client опционален (защищён от отсутствия библиотеки).
"""
from __future__ import annotations

try:
    from prometheus_client import Counter, Gauge, Histogram
except ImportError:
    # Stub — метрики не собираются, но код не падает
    class _Stub:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def __call__(self, *args, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def set(self, value):
            pass
        def observe(self, amount):
            pass

    Counter = _Stub  # type: ignore
    Gauge = _Stub   # type: ignore
    Histogram = _Stub  # type: ignore


# ── Pipeline ──
pipeline_duration = Histogram(
    "ab_pipeline_duration_seconds",
    "Pipeline duration by step",
    ["step", "status"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

pipeline_total = Counter(
    "ab_pipeline_total",
    "Pipeline runs total",
    ["status"],
)

# ── Validation ──
validation_failures = Counter(
    "ab_validation_failures_total",
    "Validation failures by error code",
    ["error_code"],
)

# ── Approval ──
approval_queue_size = Gauge(
    "ab_approval_queue_size",
    "Documents pending approval",
    ["company_id"],
)

approval_decisions = Counter(
    "ab_approval_decisions_total",
    "Approval decisions",
    ["decision"],
)

# ── Posting ──
posting_duration = Histogram(
    "ab_posting_duration_seconds",
    "Posting duration",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0),
)

posting_total = Counter(
    "ab_posting_total",
    "Posting results",
    ["result"],
)

# ── Outbox ──
outbox_backlog = Gauge(
    "ab_outbox_backlog",
    "Pending outbox events",
)

outbox_total = Counter(
    "ab_outbox_total",
    "Outbox events processed",
    ["event_type", "status"],
)

# ── Replay ──
replay_total = Counter(
    "ab_replay_total",
    "Replay runs total",
    ["mode", "status"],
)

# ── Health ──
health_status = Gauge(
    "ab_health_status",
    "Service health (1=ok, 0=down)",
    ["component"],
)
