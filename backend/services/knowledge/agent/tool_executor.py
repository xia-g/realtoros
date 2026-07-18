"""Tool Executor — выполняет инструменты через ToolRegistry и оборачивает в ToolCall."""

from __future__ import annotations

from backend.services.knowledge.agent.tool_registry import ToolRegistry
from backend.services.knowledge.agent.contracts import ToolCall


class ToolExecutor:
    """Выполняет инструменты и возвращает структурированные результаты.

    - Никогда не выбрасывает исключения.
    - Всегда возвращает ToolCall (успех или неудача).
    - Фиксирует latency и результат.
    """

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def execute_tool(self, tool_name: str, **kwargs) -> ToolCall:
        """Выполнить один инструмент и вернуть ToolCall."""
        result = await self._registry.execute(tool_name, **kwargs)
        return ToolCall(
            tool_name=tool_name,
            arguments=kwargs,
            success=result["success"],
            duration_ms=result["duration_ms"],
            result=result.get("result", ""),
            error_message=result.get("error_message", ""),
        )
