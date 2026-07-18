"""Agent runtime contracts — dataclasses for agent requests, responses, tool calls, and sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from backend.services.knowledge.agent.enums import AgentIntent, SourceType


@dataclass
class AgentRequest:
    """Входной запрос к Agent Runtime."""
    user_id: UUID
    session_id: UUID | None
    question: str
    correlation_id: str


@dataclass
class SourceReference:
    """Ссылка на источник — для explainability."""
    source_type: SourceType | str
    source_id: str
    trust_level: str = "COMMUNITY"
    score: float = 0.0
    title: str = ""


@dataclass
class ToolCall:
    """Результат выполнения одного инструмента."""
    tool_name: str
    arguments: dict
    success: bool
    duration_ms: float
    result: str = ""
    error_message: str = ""


@dataclass
class ToolPlan:
    """План выполнения инструментов для intent."""
    intent: AgentIntent
    tools: list[str]  # ordered tool names to execute


@dataclass
class AgentResponse:
    """Ответ Agent Runtime после полного цикла."""
    answer: str
    intent: AgentIntent
    tools_used: list[str]
    sources: list[SourceReference]
    cost_usd: float
    tokens: int
    latency_ms: float
    correlation_id: str
    tool_calls: list[ToolCall] = field(default_factory=list)
