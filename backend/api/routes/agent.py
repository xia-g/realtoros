"""Agent Runtime API routes.

Endpoints:
  POST /api/v1/agent/ask    — ask the agent a question
  GET  /api/v1/agent/sessions — list active sessions
  GET  /api/v1/agent/tools    — list available tools
"""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.ai.metrics import agent_rate_limit_hits_total
from backend.services.rate_limiter import RateLimiter

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


# ─── Request / Response schemas ───


class AgentAskRequest(BaseModel):
    question: str
    user_id: str | None = None
    session_id: str | None = None


class AgentAskResponse(BaseModel):
    answer: str
    intent: str
    tools_used: list[str]
    sources: list[dict]
    cost_usd: float
    tokens: int
    latency_ms: float
    correlation_id: str


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict


class ToolsListResponse(BaseModel):
    tools: list[ToolInfo]


# ─── Dependencies ───

_rate_limiter = RateLimiter()

_agent_runtime = None  # Initialised lazily


def _register_event_handlers():
    """Register domain event handlers on startup."""
    from backend.core.domain_events import get_event_bus
    from backend.core.event_handlers import register_sync_handlers
    register_sync_handlers(get_event_bus())


def _get_agent_runtime():
    """Lazy init of AgentRuntime singleton."""
    global _agent_runtime
    if _agent_runtime is None:
        from backend.services.knowledge.agent.agent_runtime import AgentRuntime
        from backend.services.knowledge.agent.intent_classifier import IntentClassifier
        from backend.services.knowledge.agent.tool_planner import ToolPlanner
        from backend.services.knowledge.agent.tool_executor import ToolExecutor
        from backend.services.knowledge.agent.tool_registry import ToolRegistry
        from backend.services.knowledge.agent.agent_tools import (
            agent_check_deal_completeness,
            agent_validate_document_package,
            agent_get_regulation,
            agent_search_client,
            agent_search_property,
            agent_search_deal,
        )

        classifier = IntentClassifier()
        planner = ToolPlanner()
        registry = ToolRegistry()

        # Register all tools
        registry.register_tool(
            name="check_deal_completeness",
            description="Проверить сделку на полноту: чекпоинты, документы, compliance score",
            handler=agent_check_deal_completeness,
            parameters={
                "deal_id": {"type": "string", "description": "UUID сделки"},
                "deal_type": {"type": "string", "description": "Тип сделки: SALE_APARTMENT, MORTGAGE, RENT"},
            },
        )
        registry.register_tool(
            name="validate_document_package",
            description="Проверить комплект документов для типа сделки",
            handler=agent_validate_document_package,
            parameters={
                "deal_type": {"type": "string", "description": "Тип сделки"},
                "uploaded_documents": {"type": "string", "description": "Загруженные документы через запятую"},
            },
        )
        registry.register_tool(
            name="get_regulation",
            description="Поиск нормативных актов (Минфин, ФНС, Росреестр, ЦБ)",
            handler=agent_get_regulation,
            parameters={
                "query": {"type": "string", "description": "Поисковый запрос"},
                "min_trust": {"type": "string", "description": "Минимальный уровень доверия: OFFICIAL, VERIFIED, COMMUNITY, LLM_GENERATED"},
            },
        )
        registry.register_tool(
            name="search_client",
            description="Поиск клиентов по имени, телефону или email",
            handler=agent_search_client,
            parameters={"query": {"type": "string", "description": "Поисковый запрос"}},
        )
        registry.register_tool(
            name="search_property",
            description="Поиск объектов недвижимости по адресу или названию",
            handler=agent_search_property,
            parameters={"query": {"type": "string", "description": "Поисковый запрос"}},
        )
        registry.register_tool(
            name="search_deal",
            description="Поиск сделок по названию или клиенту",
            handler=agent_search_deal,
            parameters={"query": {"type": "string", "description": "Поисковый запрос"}},
        )

        executor = ToolExecutor(registry)

        _agent_runtime = AgentRuntime(
            classifier=classifier,
            planner=planner,
            executor=executor,
        )

    return _agent_runtime


# Register event handlers on first import
_register_event_handlers()


# ─── Endpoints ───


@router.post("/ask", response_model=AgentAskResponse)
async def agent_ask(request: Request, body: AgentAskRequest):
    """Ask the agent a question."""
    user_id = UUID(body.user_id) if body.user_id else UUID(int=0)
    session_id = UUID(body.session_id) if body.session_id else None

    # Rate limit check
    if not _rate_limiter.check(user_id):
        agent_rate_limit_hits_total.inc()
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Limit: 10 req/min or 100 req/hour.",
        )

    from backend.services.knowledge.agent.contracts import AgentRequest

    agent_request = AgentRequest(
        user_id=user_id,
        session_id=session_id,
        question=body.question,
        correlation_id=str(uuid.uuid4()),
    )

    runtime = _get_agent_runtime()
    response = await runtime.ask(agent_request)

    return AgentAskResponse(
        answer=response.answer,
        intent=response.intent.value,
        tools_used=response.tools_used,
        sources=[{
            "source_type": s.source_type.value if hasattr(s.source_type, 'value') else str(s.source_type),
            "source_id": s.source_id,
            "trust_level": s.trust_level,
            "score": s.score,
            "title": s.title,
        } for s in response.sources],
        cost_usd=response.cost_usd,
        tokens=response.tokens,
        latency_ms=response.latency_ms,
        correlation_id=response.correlation_id,
    )


@router.get("/tools", response_model=ToolsListResponse)
async def agent_list_tools():
    """List all available agent tools."""
    runtime = _get_agent_runtime()
    from backend.services.knowledge.agent.tool_registry import ToolRegistry
    # We need access to the registry. Use the one from the runtime.
    # For now, return a static list since we register at startup.
    return ToolsListResponse(tools=[
        ToolInfo(name="check_deal_completeness", description="Проверить сделку на полноту", parameters={}),
        ToolInfo(name="validate_document_package", description="Проверить комплект документов", parameters={}),
        ToolInfo(name="get_regulation", description="Поиск нормативных актов", parameters={}),
        ToolInfo(name="search_client", description="Поиск клиентов", parameters={}),
        ToolInfo(name="search_property", description="Поиск объектов", parameters={}),
        ToolInfo(name="search_deal", description="Поиск сделок", parameters={}),
    ])
