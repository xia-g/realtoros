"""Agent runtime enums."""

from __future__ import annotations

from enum import Enum


class AgentIntent(str, Enum):
    GENERAL_QA = "general_qa"

    SEARCH_CLIENT = "search_client"
    SEARCH_PROPERTY = "search_property"
    SEARCH_DEAL = "search_deal"

    CHECK_DEAL = "check_deal"
    VALIDATE_DOCS = "validate_docs"
    REGULATION_SEARCH = "regulation_search"

    CRM_ANALYTICS = "crm_analytics"


class SourceType(str, Enum):
    KNOWLEDGE_GRAPH = "knowledge_graph"
    DOCUMENT = "document"
    REGULATION = "regulation"
    MEMORY = "memory"
    SEARCH_RESULT = "search_result"