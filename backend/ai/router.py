"""AI Router — maps TaskType to providers with fallback chain.

Uses typed TaskType enum. No free-form strings allowed.
"""

from __future__ import annotations

import asyncio
from enum import Enum

from backend.ai.providers.base import AIProviderResponse, TaskType
from backend.ai.provider_registry import get_primary, get_fallback
from backend.core.logging import get_logger
from backend.ai.metrics import ai_budget_rejections_total, ai_provider_failures_total

logger = get_logger("integration")

TASK_ROUTING = {
    TaskType.CLASSIFICATION: {"provider": "primary", "max_tokens": 512, "temperature": 0.1},
    TaskType.EXTRACTION: {"provider": "primary", "max_tokens": 4096, "temperature": 0.1},
    TaskType.ENTITY_RESOLUTION: {"provider": "primary", "max_tokens": 1024, "temperature": 0.1},
    TaskType.RAG_ANSWER: {"provider": "primary", "max_tokens": 4096, "temperature": 0.3},
    TaskType.SUMMARIZATION: {"provider": "primary", "max_tokens": 2048, "temperature": 0.3},
    TaskType.CHAT: {"provider": "auto", "max_tokens": 4096, "temperature": 0.3},
}


async def route(
    task_type: TaskType,
    prompt: str,
    system_prompt: str = "",
    correlation_id: str = "",
    cost_tracker=None,
    user_id: str | None = None,
) -> AIProviderResponse:
    """Route a typed task to the appropriate provider with fallback.

    Args:
        task_type: Enum member from TaskType (CLASSIFICATION, EXTRACTION, etc.)
        prompt: Text prompt
        system_prompt: Optional system instructions
        correlation_id: Trace ID for audit
        cost_tracker: Optional CostTracker for budget enforcement
        user_id: Required if cost_tracker is provided
    """
    config = TASK_ROUTING.get(task_type, TASK_ROUTING[TaskType.CHAT])
    max_tokens = config["max_tokens"]
    temperature = config["temperature"]

    providers = []
    if config["provider"] in ("primary", "auto"):
        p = get_primary()
        if p:
            providers.append(p)
    if config["provider"] in ("fallback", "auto"):
        f = get_fallback()
        if f:
            providers.append(f)

    if not providers:
        logger.error("no_providers_available", task_type=task_type.value)
        ai_provider_failures_total.labels(provider="none", error_type="no_providers").inc()
        return AIProviderResponse(
            content="", provider="none", model_name="none",
            task_type=task_type.value, status="error",
            error_message="No AI providers available",
        )

    last_error = None
    for provider in providers:
        if cost_tracker and user_id:
            estimated = provider.estimate_cost(len(prompt) // 3 + max_tokens, max_tokens // 2)
            allowed = await cost_tracker.check_and_reserve(user_id, estimated)
            if not allowed:
                ai_budget_rejections_total.labels(level="user").inc()
                logger.warning("budget_rejected", provider=provider.name, user_id=user_id)
                continue

        try:
            result = await asyncio.wait_for(
                provider.chat(prompt=prompt, system_prompt=system_prompt,
                              max_tokens=max_tokens, temperature=temperature,
                              correlation_id=correlation_id),
                timeout=65,
            )
            if result.status == "success":
                logger.info("provider_success", provider=provider.name, task_type=task_type.value, cost=result.cost_usd)
                return result
            logger.warning("provider_returned_error", provider=provider.name, status=result.status, error=result.error_message)
            ai_provider_failures_total.labels(provider=provider.name, error_type=result.status).inc()
            last_error = result.error_message
        except asyncio.TimeoutError:
            logger.warning("provider_timed_out", provider=provider.name)
            ai_provider_failures_total.labels(provider=provider.name, error_type="timeout").inc()
            last_error = f"{provider.name} timed out"

    logger.error("all_providers_failed", task_type=task_type.value, last_error=last_error)
    ai_provider_failures_total.labels(provider="all", error_type="all_failed").inc()
    return AIProviderResponse(
        content="", provider="none", model_name="none",
        task_type=task_type.value, status="error",
        error_message=f"All providers failed: {last_error}",
    )