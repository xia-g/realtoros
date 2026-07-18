"""Security layer Prometheus metrics.

All metrics use low-cardinality labels only. No user_id or session_id labels.
"""

from __future__ import annotations

from backend.ai.metrics import (
    knowledge_security_scans_total,
    knowledge_security_findings_total,
    knowledge_security_critical_total,
    knowledge_security_sanitized_total,
    knowledge_security_scan_duration_seconds,
    knowledge_injection_attempts_total,
    knowledge_regulation_security_events_total,
)

__all__ = [
    "knowledge_security_scans_total",
    "knowledge_security_findings_total",
    "knowledge_security_critical_total",
    "knowledge_security_sanitized_total",
    "knowledge_security_scan_duration_seconds",
    "knowledge_injection_attempts_total",
    "knowledge_regulation_security_events_total",
]
