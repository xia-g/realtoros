"""
Settings — environment-driven configuration.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки Accounting Binding."""
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/accounting_binding.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = True
    METRICS_PORT: int = 9091
    WORKERS: int = 4

    model_config = {"env_prefix": "AB_", "env_file": ".env"}


settings = Settings()
