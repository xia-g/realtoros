"""Agent Runtime — main orchestrator for Sprint 4 P6.

Pipeline:
  1 classify intent
  2 load memory
  3 create plan
  4 execute tools
  5 build context
  6 call AIRouter
  7 save memory
  8 audit & metrics
  9 return response
"""

from __future__ import annotations

import time
import uuid
from uuid import UUID

from structlog import get_logger

from backend.services.knowledge.agent.enums import AgentIntent, SourceType
from backend.core.agent_budget import AgentExecutionBudget, AgentExecutionLimitExceeded
from backend.services.knowledge.agent.contracts import (
    AgentRequest,
    AgentResponse,
    SourceReference,
    ToolCall,
)
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
from backend.ai.metrics import (
    agent_requests_total,
    agent_request_duration_seconds,
    agent_tool_calls_total,
    agent_tool_failures_total,
    agent_intent_total,
    agent_response_tokens_total,
    agent_rate_limit_hits_total,
    agent_limit_hit_total,
)

logger = get_logger(__name__)


class AgentRuntime:
    """Главный оркестратор Agent Runtime.

    Собирает все компоненты в единый pipeline.
    """

    def __init__(
        self,
        classifier: IntentClassifier,
        planner: ToolPlanner,
        executor: ToolExecutor,
        context_builder=None,
        ai_audit_service=None,
        cost_tracker=None,
        tool_audit_service=None,
        ai_router=None,
    ):
        self._classifier = classifier
        self._planner = planner
        self._executor = executor
        self._context_builder = context_builder
        self._ai_audit = ai_audit_service
        self._cost_tracker = cost_tracker
        self._tool_audit = tool_audit_service
        self._ai_router = ai_router

    async def ask(self, request: AgentRequest) -> AgentResponse:
        """Полный цикл обработки вопроса."""
        start = time.monotonic()
        correlation_id = request.correlation_id or str(uuid.uuid4())

        logger.info(
            "agent_request_start",
            correlation_id=correlation_id,
            intent=None,
            question_len=len(request.question),
        )

        # 0. Initialize execution budget
        budget = AgentExecutionBudget()
        budget.chain_depth = 1

        # 1. Classify intent
        intent = self._classifier.classify(request.question)
        agent_intent_total.labels(intent=intent.value).inc()

        # 2. Create plan
        plan = self._planner.plan(intent, request.question)

        # 3. Execute tools
        tool_calls: list[ToolCall] = []
        for tool_name in plan.tools:
            # Enforce execution budget
            budget.tool_calls_used = len(tool_calls)
            try:
                budget.check()
            except AgentExecutionLimitExceeded as e:
                logger.warning("agent_budget_exceeded", tool=tool_name, error=str(e))
                agent_limit_hit_total.inc()
                break

            executor_result = await self._executor.execute_tool(tool_name)
            tool_calls.append(executor_result)
            agent_tool_calls_total.labels(tool_name=tool_name).inc()
            if not executor_result.success:
                agent_tool_failures_total.labels(tool_name=tool_name).inc()

            # Audit tool call
            if self._tool_audit:
                await self._tool_audit.log_call(
                    correlation_id=correlation_id,
                    user_id=request.user_id,
                    tool_name=tool_name,
                    duration_ms=executor_result.duration_ms,
                    success=executor_result.success,
                    session_id=request.session_id,
                    input_hash=ToolRegistry.input_hash(request.question),
                    error_message=executor_result.error_message if not executor_result.success else None,
                )

        # 4. Build context (if context builder available)
        context_output = None
        if self._context_builder:
            from backend.services.knowledge.context.contracts import ContextBuilderInput

            cb_input = ContextBuilderInput(
                query=request.question,
                user_id=request.user_id,
                session_id=request.session_id,
                correlation_id=correlation_id,
            )
            context_output = await self._context_builder.build(cb_input)

        # 5. Prepare prompt from context or tools
        answer = ""
        tokens = 0
        cost = 0.0

        # If tools were executed, build answer from tool results
        if tool_calls:
            answer_parts = []
            for tc in tool_calls:
                if tc.success and tc.result:
                    answer_parts.append(f"## {tc.tool_name}\n{tc.result}")
                elif not tc.success:
                    answer_parts.append(f"## {tc.tool_name}\nОшибка: {tc.error_message}")

            answer = "\n\n".join(answer_parts)

            # If we have an AI router and context, use LLM to generate final response
            if self._ai_router and context_output and answer:
                llm_prompt = f"""Ты — ассистент агентства недвижимости. Отвечай на русском языке.

Контекст:
{context_output.prompt}

Результаты выполнения инструментов:
{answer}

Ответь пользователю на его вопрос на основе контекста и результатов инструментов.
"""
                llm_result = await self._ai_router("general_qa", llm_prompt)
                if llm_result and "content" in llm_result:
                    answer = llm_result["content"]
                    tokens = llm_result.get("total_tokens", 0)
                    cost = llm_result.get("cost_usd", 0.0)

                    # Audit LLM call
                    if self._ai_audit:
                        await self._ai_audit.record_call(
                            prompt=llm_prompt,
                            response=answer,
                            provider=llm_result.get("provider", "deepseek"),
                            model=llm_result.get("model", "deepseek-flash"),
                            input_tokens=llm_result.get("input_tokens", 0),
                            output_tokens=llm_result.get("output_tokens", 0),
                            total_tokens=tokens,
                            cost_usd=cost,
                            latency_ms=llm_result.get("latency_ms", 0),
                            correlation_id=correlation_id,
                            user_id=str(request.user_id),
                            session_id=str(request.session_id) if request.session_id else None,
                            task_type=plan.intent.value,
                        )

        # 6. Build sources
        sources = []
        for tc in tool_calls:
            sources.append(SourceReference(
                source_type=SourceType.SEARCH_RESULT,
                source_id=tc.tool_name,
                trust_level="VERIFIED",
                score=1.0 if tc.success else 0.0,
                title=tc.tool_name,
            ))

        if context_output and context_output.provenance:
            for p in context_output.provenance:
                sources.append(SourceReference(
                    source_type=p.source_type,
                    source_id=str(p.source_id),
                    trust_level="VERIFIED",
                    score=p.score,
                    title=p.snippet[:100] if p.snippet else "",
                ))

        # 7. Build response
        latency = (time.monotonic() - start) * 1000
        tools_used = [tc.tool_name for tc in tool_calls]

        # Sort sources: OFFICIAL > VERIFIED > COMMUNITY > LLM_GENERATED
        trust_order = {"OFFICIAL": 4, "VERIFIED": 3, "COMMUNITY": 2, "LLM_GENERATED": 1}
        sources.sort(key=lambda s: trust_order.get(s.trust_level, 0), reverse=True)

        response = AgentResponse(
            answer=answer,
            intent=intent,
            tools_used=tools_used,
            sources=sources,
            cost_usd=cost,
            tokens=tokens,
            latency_ms=round(latency, 2),
            correlation_id=correlation_id,
            tool_calls=tool_calls,
        )

        # 8. Metrics
        agent_requests_total.labels(intent=intent.value).inc()
        agent_request_duration_seconds.observe(latency / 1000)
        agent_response_tokens_total.observe(tokens)

        logger.info(
            "agent_request_complete",
            correlation_id=correlation_id,
            intent=intent.value,
            tools=tools_used,
            latency_ms=round(latency, 2),
        )

        return response
