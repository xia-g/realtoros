"""Agent Runtime Safety Limits — resolves C5 from Sprint 8.7 audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


class AgentExecutionLimitExceeded(Exception):
    """Raised when agent exceeds execution limits."""


@dataclass
class AgentExecutionBudget:
    """Tracks agent execution against limits."""
    max_tool_calls: int = 10
    max_chain_depth: int = 3
    max_total_seconds: int = 30
    max_context_rebuilds: int = 2

    tool_calls_used: int = 0
    chain_depth: int = 0
    context_rebuilds: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def check(self) -> None:
        if self.tool_calls_used >= self.max_tool_calls:
            raise AgentExecutionLimitExceeded(
                f"Tool call limit ({self.max_tool_calls}) exceeded"
            )
        if self.chain_depth >= self.max_chain_depth:
            raise AgentExecutionLimitExceeded(
                f"Chain depth limit ({self.max_chain_depth}) exceeded"
            )
        if self.elapsed_seconds >= self.max_total_seconds:
            raise AgentExecutionLimitExceeded(
                f"Runtime limit ({self.max_total_seconds}s) exceeded"
            )
        if self.context_rebuilds >= self.max_context_rebuilds:
            raise AgentExecutionLimitExceeded(
                f"Context rebuild limit ({self.max_context_rebuilds}) exceeded"
            )
