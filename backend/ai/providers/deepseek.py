"""DeepSeek Flash provider — with retry and circuit breaker."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import httpx

from backend.ai.providers.base import AIProvider, AIProviderResponse
from backend.config import settings
from backend.core.logging import get_logger
from backend.ai.metrics import ai_provider_failures_total

logger = get_logger("integration")

DEEPSEEK_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 2
CIRCUIT_BREAKER_THRESHOLD = 5      # consecutive failures
CIRCUIT_BREAKER_TIMEOUT = 60        # seconds


class CircuitState:
    def __init__(self):
        self.failures = 0
        self.state = "closed"  # closed, open, half-open
        self.last_open: datetime | None = None

    def record_success(self):
        self.failures = 0
        self.state = "closed"

    def record_failure(self):
        self.failures += 1
        if self.failures >= CIRCUIT_BREAKER_THRESHOLD:
            self.state = "open"
            self.last_open = datetime.now(timezone.utc)
            logger.warning("circuit_breaker_opened", provider="deepseek", failures=self.failures)

    def is_open(self) -> bool:
        if self.state == "open" and self.last_open:
            if (datetime.now(timezone.utc) - self.last_open).total_seconds() > CIRCUIT_BREAKER_TIMEOUT:
                self.state = "half-open"
                logger.info("circuit_breaker_half_open", provider="deepseek")
                return False
            return True
        return False


_circuit = CircuitState()


class DeepSeekProvider(AIProvider):
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=DEEPSEEK_BASE,
            headers={"Authorization": f"Bearer {settings.AI_DEEPSEEK_API_KEY}"},
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
        )

    @property
    def name(self) -> str: return "deepseek"
    @property
    def model_name(self) -> str: return DEEPSEEK_MODEL

    async def health_check(self) -> bool:
        return not _circuit.is_open()

    async def chat(self, prompt="", system_prompt="", max_tokens=2048, temperature=0.3, correlation_id="") -> AIProviderResponse:
        if _circuit.is_open():
            ai_provider_failures_total.labels(provider="deepseek", error_type="circuit_open").inc()
            return AIProviderResponse(content="", provider=self.name, model_name=self.model_name,
                                       task_type="chat", status="error", error_message="Circuit breaker open")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(1, MAX_RETRIES + 2):
            start = time.monotonic()
            try:
                resp = await self._client.post("/chat/completions", json={
                    "model": DEEPSEEK_MODEL, "messages": messages,
                    "max_tokens": max_tokens, "temperature": temperature,
                })
                elapsed = int((time.monotonic() - start) * 1000)

                if resp.status_code in RETRY_STATUSES and attempt <= MAX_RETRIES:
                    wait = 2 ** attempt
                    logger.warning("deepseek_retry", status=resp.status_code, attempt=attempt, wait=wait)
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                usage = data.get("usage", {})
                _circuit.record_success()
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
                last_error = "timeout"
                logger.warning("deepseek_timeout", attempt=attempt, elapsed=elapsed)
                if attempt <= MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in RETRY_STATUSES:
                    _circuit.record_failure()
                    elapsed = int((time.monotonic() - start) * 1000)
                    return AIProviderResponse(content="", provider=self.name, model_name=self.model_name,
                                               task_type="chat", latency_ms=elapsed,
                                               status="error", error_message=f"HTTP {e.response.status_code}")
                last_error = f"HTTP {e.response.status_code}"
                if attempt <= MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                elapsed = int((time.monotonic() - start) * 1000)
                last_error = str(e)
                if attempt <= MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)

        _circuit.record_failure()
        return AIProviderResponse(content="", provider=self.name, model_name=self.model_name,
                                   task_type="chat", status="error", error_message=last_error)

    def estimate_cost(self, prompt_tokens=0, completion_tokens=0) -> float:
        return (prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000