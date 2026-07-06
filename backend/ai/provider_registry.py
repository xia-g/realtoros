"""Provider registry — register and resolve AI providers by task."""

from __future__ import annotations

from backend.ai.providers.base import AIProvider
from backend.ai.providers.deepseek import DeepSeekProvider
from backend.ai.providers.openai_provider import OpenAIProvider
from backend.core.logging import get_logger

logger = get_logger("integration")

_primary_provider: AIProvider | None = None
_fallback_provider: AIProvider | None = None
_custom_providers: dict[str, AIProvider] = {}


def register_primary(provider: AIProvider) -> None:
    global _primary_provider
    _primary_provider = provider
    logger.info("provider_registered_primary", name=provider.name, model=provider.model_name)


def register_fallback(provider: AIProvider) -> None:
    global _fallback_provider
    _fallback_provider = provider
    logger.info("provider_registered_fallback", name=provider.name, model=provider.model_name)


def register(name: str, provider: AIProvider) -> None:
    _custom_providers[name] = provider
    logger.info("provider_registered", name=name, model=provider.model_name)


def get_primary() -> AIProvider | None:
    return _primary_provider


def get_fallback() -> AIProvider | None:
    return _fallback_provider


def get_provider(name: str) -> AIProvider | None:
    if _primary_provider and _primary_provider.name == name:
        return _primary_provider
    if _fallback_provider and _fallback_provider.name == name:
        return _fallback_provider
    return _custom_providers.get(name)


def initialize():
    """Register default providers at startup."""
    register_primary(DeepSeekProvider())
    register_fallback(OpenAIProvider())
    logger.info("provider_registry_initialized", primary="deepseek", fallback="openai")