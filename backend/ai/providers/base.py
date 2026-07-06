"""Abstract AI provider contract.

All providers must implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    ENTITY_RESOLUTION = "entity_resolution"
    RAG_ANSWER = "rag_answer"
    SUMMARIZATION = "summarization"
    CHAT = "chat"

    def __str__(self):
        return self.value


@dataclass
class AIProviderResponse:
    content: str = ""
    provider: str = ""
    model_name: str = ""
    task_type: str = "chat"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    finish_reason: str = ""  # stop, length, content_filter, tool_calls
    status: str = "success"  # success, error, timeout
    error_message: str | None = None
    correlation_id: str = ""


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def chat(self, prompt: str = "", system_prompt: str = "", max_tokens: int = 2048,
                   temperature: float = 0.3, correlation_id: str = "") -> AIProviderResponse: ...

    @abstractmethod
    def estimate_cost(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> float: ...

    def supports_task(self, task_type: str) -> bool:
        return True