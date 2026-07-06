"""
Observability — Health Model.

Отдельные endpoints для health/readiness/liveness/dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class DependencyCheck(Protocol):
    """Интерфейс проверки зависимости."""
    async def check(self) -> dict[str, Any]:
        ...


@dataclass
class HealthStatus:
    """Состояние здоровья сервиса."""
    status: str  # ok, degraded, down
    version: str = "1.3.0"
    timestamp: str = ""
    checks: dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """Проверка health/readiness/liveness/dependencies.

    - liveness: сервис жив (быстрая проверка)
    - readiness: сервис готов принимать трафик
    - health: полная диагностика
    - dependencies: внешние зависимости
    """

    def __init__(self):
        self._dependencies: dict[str, DependencyCheck] = {}

    def register(self, name: str, check: DependencyCheck) -> None:
        """Зарегистрировать проверку зависимости."""
        self._dependencies[name] = check

    async def liveness(self) -> dict[str, Any]:
        """Сервис жив?"""
        return {"status": "ok", "version": "1.3.0"}

    async def readiness(self) -> dict[str, Any]:
        """Сервис готов?"""
        all_ok = True
        deps: dict[str, Any] = {}
        for name, check in self._dependencies.items():
            try:
                result = await check.check()
                deps[name] = result
                if result.get("status") != "ok":
                    all_ok = False
            except Exception as e:
                deps[name] = {"status": "error", "error": str(e)}
                all_ok = False

        return {
            "status": "ok" if all_ok else "degraded",
            "dependencies": deps,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def health(self) -> dict[str, Any]:
        """Полная диагностика."""
        readiness = await self.readiness()
        return {
            "status": readiness["status"],
            "version": "1.3.0",
            "dependencies": readiness["dependencies"],
            "uptime_seconds": 0,  # TODO: track
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def dependencies(self) -> dict[str, Any]:
        """Только внешние зависимости."""
        result: dict[str, Any] = {}
        for name, check in self._dependencies.items():
            try:
                dep_result = await check.check()
                result[name] = dep_result
            except Exception as e:
                result[name] = {"status": "error", "error": str(e)}
        return result
