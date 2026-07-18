"""Retry policy for processing failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class RetryPolicy:
    """Backoff retry configuration."""

    max_attempts: int = 5
    initial_backoff_sec: float = 10.0
    backoff_multiplier: float = 2.0
    max_backoff_sec: float = 1800.0  # 30 min

    def get_next_retry_at(self, attempt_count: int) -> datetime:
        """Calculate the next retry time based on exponential backoff."""
        if attempt_count >= self.max_attempts:
            return None  # Dead letter — no more retries

        delay = self.initial_backoff_sec * (self.backoff_multiplier ** attempt_count)
        delay = min(delay, self.max_backoff_sec)
        return datetime.now(timezone.utc) + timedelta(seconds=delay)

    def should_dlq(self, attempt_count: int) -> bool:
        """Returns True if the event should be moved to dead letter queue."""
        return attempt_count >= self.max_attempts


DEFAULT_RETRY = RetryPolicy()
