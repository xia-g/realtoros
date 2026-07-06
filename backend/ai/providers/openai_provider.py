"""OpenAI GPT-4o provider — fallback with retry."""

from __future__ import annotations

import asyncio
import time

import httpx

from backend.ai.providers.base import AIProvider, AIProviderResponse
from backend.config import settings
from backend.core.logging import get_logger

logger = get_logger("integration")

OPENAI_BASE = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o"
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 1


class OpenAIProvider(AIProvider):
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=OPENAI_BASE,
            headers={"Authorization": f"Bearer {settings.AI_CHATGPT_API_KEY}"},
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
        )

    @property
    def name(self) -> str: return "openai"
    @property
    def model_name(self) -> str: return OPENAI_MODEL

    async def health_check(self) -> bool:
        return True

    async def chat(self, prompt="", system_prompt="", max_tokens=2048, temperature=0.3, correlation_id="") -> AIProviderResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(1, MAX_RETRIES + 2):
            start = time.monotonic()
            try:
                resp = await self._client.post("/chat/completions", json={
                    "model": OPENAI_MODEL, "messages": messages,
                    "max_tokens": max_tokens, "temperature": temperature,
                })
                elapsed = int((time.monotonic() - start) * 1000)
                if resp.status_code in RETRY_STATUSES and attempt <= MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                usage = data.get("usage", {})
                return AIProviderResponse(
                    content=choice["message"]["content"],
                    provider=self.name, model_name=self.model_name, task_type="chat",
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    cost_usd=self.estimate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                    latency_ms=elapsed, finish_reason=choice.get("finish_reason", ""),
                    status="success",
                )
            except httpx.TimeoutException:
                elapsed = int((time.monotonic() - start) * 1000)
                if attempt <= MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return AIProviderResponse(content="", provider=self.name, model_name=self.model_name,
                                               task_type="chat", latency_ms=elapsed,
                                               status="timeout", error_message="OpenAI timeout")
            except Exception as e:
                elapsed = int((time.monotonic() - start) * 1000)
                if attempt <= MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return AIProviderResponse(content="", provider=self.name, model_name=self.model_name,
                                               task_type="chat", latency_ms=elapsed,
                                               status="error", error_message=str(e))

        return AIProviderResponse(content="", provider=self.name, model_name=self.model_name,
                                   task_type="chat", status="error", error_message="Max retries exceeded")

    def estimate_cost(self, prompt_tokens=0, completion_tokens=0) -> float:
        return (prompt_tokens * 2.50 + completion_tokens * 10.00) / 1_000_000