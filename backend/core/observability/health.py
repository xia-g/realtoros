"""Health check framework with pluggable check providers.

Each check implements HealthCheckInterface.
HealthService.run_all() aggregates all registered checks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import text

from backend.database import async_session_factory
from backend.core.logging import get_logger

logger = get_logger("app")


class HealthCheckInterface(ABC):
    """Interface for pluggable health checks."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique check name used in health response."""
        ...

    @abstractmethod
    async def check(self) -> dict[str, Any]:
        """Run the check and return status information."""
        ...


class DatabaseHealthCheck(HealthCheckInterface):
    """Verifies database connectivity via a simple SELECT 1."""

    @property
    def name(self) -> str:
        return "database"

    async def check(self) -> dict[str, Any]:
        try:
            async with async_session_factory() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar_one()
                return {"status": "connected"}
        except Exception as exc:
            logger.error("database_health_check_failed", error=str(exc))
            return {"status": "disconnected", "error": str(exc)}


class AIHealthCheck(HealthCheckInterface):
    """Future: verify AI model availability."""

    @property
    def name(self) -> str:
        return "ai"

    async def check(self) -> dict[str, Any]:
        return {"status": "not_implemented"}


class EmbeddingHealthCheck(HealthCheckInterface):
    """Future: verify embedding service availability."""

    @property
    def name(self) -> str:
        return "embedding"

    async def check(self) -> dict[str, Any]:
        return {"status": "not_implemented"}


class TelegramHealthCheck(HealthCheckInterface):
    """Future: verify Telegram bot connectivity."""

    @property
    def name(self) -> str:
        return "telegram"

    async def check(self) -> dict[str, Any]:
        return {"status": "not_implemented"}


# Registry of all health checks
_REGISTERED_CHECKS: list[HealthCheckInterface] = [
    DatabaseHealthCheck(),
    AIHealthCheck(),
    EmbeddingHealthCheck(),
    TelegramHealthCheck(),
]


class HealthService:
    """Aggregates all registered health checks."""

    @staticmethod
    async def check_all() -> dict[str, Any]:
        results: dict[str, Any] = {"status": "ok", "checks": {}}
        all_ok = True

        for check in _REGISTERED_CHECKS:
            try:
                result = await check.check()
                results["checks"][check.name] = result
                if result.get("status") not in ("connected", "ok", "not_implemented"):
                    all_ok = False
            except Exception as exc:
                results["checks"][check.name] = {"status": "error", "error": str(exc)}
                all_ok = False

        results["status"] = "ok" if all_ok else "degraded"
        results["version"] = "0.2.0"
        return results
