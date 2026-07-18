"""Tool Registry — centralised registry of all agent tools.

Runtime must never call tools directly. Only through registry.
"""

from __future__ import annotations

import time
import hashlib
from typing import Any, Callable

from structlog import get_logger

logger = get_logger(__name__)


class ToolRegistration:
    """Метаданные зарегистрированного инструмента."""
    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        parameters: dict | None = None,
    ):
        self.name = name
        self.description = description
        self.handler = handler
        self.parameters = parameters or {}


class ToolRegistry:
    """Центральный реестр инструментов агента.

    Все инструменты регистрируются через register_tool().
    Выполнение — только через execute().
    """

    def __init__(self):
        self._tools: dict[str, ToolRegistration] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        parameters: dict | None = None,
    ) -> None:
        """Зарегистрировать инструмент."""
        if name in self._tools:
            logger.warning("tool_replaced", tool_name=name)
        self._tools[name] = ToolRegistration(name, description, handler, parameters)
        logger.info("tool_registered", tool_name=name)

    def get_tool(self, name: str) -> ToolRegistration | None:
        """Получить инструмент по имени."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """Список всех инструментов с описанием."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in sorted(self._tools.values(), key=lambda x: x.name)
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def execute(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> dict:
        """Выполнить инструмент.

        Returns:
            dict с ключами:
            - success: bool
            - result: str (JSON)
            - duration_ms: float
            - error_message: str (если failed)
        """
        start = time.monotonic()
        tool = self._tools.get(tool_name)

        if tool is None:
            duration = (time.monotonic() - start) * 1000
            logger.error("tool_not_found", tool_name=tool_name)
            return {
                "success": False,
                "result": "",
                "duration_ms": round(duration, 2),
                "error_message": f"Tool '{tool_name}' not found",
            }

        try:
            result_raw = tool.handler(**kwargs)
            duration = (time.monotonic() - start) * 1000

            if isinstance(result_raw, str):
                result_str = result_raw
            else:
                result_str = str(result_raw)

            logger.info("tool_executed", tool_name=tool_name, duration_ms=round(duration, 2))
            return {
                "success": True,
                "result": result_str,
                "duration_ms": round(duration, 2),
                "error_message": "",
            }

        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            logger.error("tool_execution_failed", tool_name=tool_name, error=str(e))
            return {
                "success": False,
                "result": "",
                "duration_ms": round(duration, 2),
                "error_message": str(e),
            }

    @staticmethod
    def input_hash(text: str) -> str:
        """SHA256 хеш входных данных (для audit)."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
