"""Application configuration via environment variables.

Single source of truth for all configuration.
Loaded from .env file at project root.
All settings validated by Pydantic.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/real_estate_os"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/real_estate_os"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ── App ───────────────────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8090
    APP_DEBUG: bool = True
    APP_TITLE: str = "Real Estate OS API"
    APP_VERSION: str = "0.2.0"
    APP_DESCRIPTION: str = "AI-платформа для агентства недвижимости"

    # ── Security ──────────────────────────────────────────────────
    SECRET_KEY: str                          # REQUIRED: set in .env. No default.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h
    JWT_ALGORITHM: str = "HS256"

    # ── Telegram ──────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    REVIEW_GROUP_CHAT_ID: str = ""

    # ── AI Models ─────────────────────────────────────────────────
    AI_DEEPSEEK_API_KEY: str = ""
    AI_QWEN_ENDPOINT: str = "http://localhost:8001/v1"
    AI_DEEPSEEK_FLASH: str = "deepseek-chat"
    AI_DEEPSEEK_PRO: str = "deepseek-reasoner"
    AI_CHATGPT_API_KEY: str                  # REQUIRED: set in .env. No default.
    AI_EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"

    # ── Lead Scoring ──────────────────────────────────────────────
    LEAD_SCORE_RULE_HOT: float = 0.80
    LEAD_SCORE_RULE_WARM: float = 0.60
    LEAD_SCORE_RULE_COLD: float = 0.30
    LEAD_AUTO_ASSIGN_THRESHOLD: float = 0.80
    LEAD_EXPIRY_DAYS: int = 30
    LEAD_MAX_REOPEN: int = 3

    # ── Integrations ──────────────────────────────────────────────
    AVITO_API_KEY: str = ""
    CIAN_API_KEY: str = ""

    # ── Security Layer (P5) ───────────────────────────────────────
    SECURITY_ENABLED: bool = True
    SECURITY_MAX_FINDINGS: int = 100
    SECURITY_CRITICAL_THRESHOLD: int = 6
    SECURITY_SANITIZE_XML: bool = True
    SECURITY_SANITIZE_CDATA: bool = True
    SECURITY_LOG_SNIPPET_LENGTH: int = 100


settings = Settings()
