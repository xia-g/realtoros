"""AI audit service — logs every provider call to ai_call_log.

Logs BOTH success and failure. Never logs raw prompt/response content.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from backend.ai.providers.base import AIProviderResponse
from backend.core.logging import get_logger
from backend.models.ai_call_log import AIQueryLog
from backend.repositories.ai_query_log_repository import AIQueryLogRepository
from backend.ai.metrics import ai_calls_total, ai_cost_total, ai_latency_seconds

logger = get_logger("audit")


def _redact(text: str, max_len: int = 100) -> str:
    """Redact sensitive content. Returns hash + snippet."""
    if not text:
        return ""
    h = hashlib.sha256(text.encode()).hexdigest()[:12]
    snippet = text[:max_len].replace("\n", " ")
    return f"[hash:{h}] {snippet}..."


class AIAuditService:
    """Audit every AI call — success and failure. Never logs raw prompts."""

    def __init__(self, session):
        self.session = session
        self.repo = AIQueryLogRepository(session)

    async def record_call(
        self,
        response: AIProviderResponse,
        correlation_id: str,
        user_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> AIQueryLog:
        log_entry = AIQueryLog(
            correlation_id=correlation_id[:16],
            provider=response.provider,
            model_name=response.model_name,
            task_type=response.task_type,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            cost_usd=response.cost_usd,
            latency_ms=response.latency_ms,
            status=response.status,
            error_message=response.error_message[:500] if response.error_message else None,
            user_id=user_id,
            metadata=metadata,
        )
        self.session.add(log_entry)
        await self.session.flush()

        # Metrics — always emitted, even on failure
        ai_calls_total.labels(provider=response.provider, model=response.model_name,
                              status=response.status).inc()
        ai_cost_total.labels(provider=response.provider, model=response.model_name).inc(response.cost_usd)
        ai_latency_seconds.labels(provider=response.provider, model=response.model_name).observe(
            response.latency_ms / 1000.0
        )

        # Audit log — redacted content
        logger.info(
            "ai.model_invoked",
            provider=response.provider,
            model=response.model_name,
            task_type=response.task_type,
            tokens=response.total_tokens,
            cost=round(response.cost_usd, 6),
            latency_ms=response.latency_ms,
            status=response.status,
            finish_reason=response.finish_reason,
            error=response.error_message[:100] if response.error_message else None,
            correlation_id=correlation_id,
            user_id=str(user_id) if user_id else None,
        )
        return log_entry