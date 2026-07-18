"""
KnowledgeRevisionNumber — immutable revision counter.

NO logic. Pure validation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeRevisionNumber:
    """Номер ревизии. Immutable. validation >= 0."""
    number: int

    def __post_init__(self) -> None:
        if self.number < 0:
            raise ValueError(f"Revision number must be >= 0, got {self.number}")

    @property
    def is_initial(self) -> bool:
        return self.number == 0
