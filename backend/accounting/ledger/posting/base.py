"""PostingRule base — all posting rules implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PostingLine:
    account_code: str
    direction: str  # debit | credit
    amount: float
    currency: str = "RUB"


@dataclass
class PostingResult:
    rule_code: str
    lines: list[PostingLine] = field(default_factory=list)

    def validate(self) -> None:
        debit = sum(l.amount for l in self.lines if l.direction == "debit")
        credit = sum(l.amount for l in self.lines if l.direction == "credit")
        if abs(debit - credit) > 0.01:
            raise ValueError(f"Posting imbalance: debit={debit} credit={credit}")


class PostingRule(ABC):
    rule_code: str = ""
    priority: int = 0
    description: str = ""

    @abstractmethod
    def supports(self, event_type: str, decision: dict, explanations: list[dict]) -> bool:
        ...

    @abstractmethod
    def generate(self, event_type: str, decision: dict, explanations: list[dict]) -> PostingResult:
        ...
