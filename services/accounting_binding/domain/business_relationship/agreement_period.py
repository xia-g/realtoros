"""
AgreementPeriod — time period for an Agreement or Participant.

Immutable value object. Validates start ≤ end.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AgreementPeriod:
    """Период действия. Immutable. start_date ≤ end_date."""
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError(
                f"start_date ({self.start_date}) must not be after "
                f"end_date ({self.end_date})"
            )

    def is_active_on(self, d: date) -> bool:
        """Check if period is active on given date."""
        if self.start_date and d < self.start_date:
            return False
        if self.end_date and d > self.end_date:
            return False
        return True

    @classmethod
    def from_dates(cls, start: date | None, end: date | None) -> AgreementPeriod:
        return cls(start_date=start, end_date=end)
