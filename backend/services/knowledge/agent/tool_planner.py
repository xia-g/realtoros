"""Tool Planner — rule-based V1.

Определяет, какие инструменты выполнить для каждого intent.
Детерминированно. 100% тестируемо.
"""

from __future__ import annotations

from backend.services.knowledge.agent.enums import AgentIntent
from backend.services.knowledge.agent.contracts import ToolPlan


# Карта intent → список инструментов
INTENT_TOOL_MAP: dict[AgentIntent, list[str]] = {
    AgentIntent.GENERAL_QA: [],

    AgentIntent.SEARCH_CLIENT: ["search_client"],
    AgentIntent.SEARCH_PROPERTY: ["search_property"],
    AgentIntent.SEARCH_DEAL: ["search_deal"],

    AgentIntent.CHECK_DEAL: ["check_deal_completeness"],
    AgentIntent.VALIDATE_DOCS: ["validate_document_package"],
    AgentIntent.REGULATION_SEARCH: ["get_regulation"],

    AgentIntent.CRM_ANALYTICS: [],
}


class ToolPlanner:
    """Планировщик инструментов.

    Input: question + intent
    Output: ToolPlan с упорядоченным списком инструментов.
    """

    def plan(self, intent: AgentIntent, question: str = "") -> ToolPlan:
        """Создать план выполнения для заданного intent."""
        tools = list(INTENT_TOOL_MAP.get(intent, []))
        return ToolPlan(intent=intent, tools=tools)
