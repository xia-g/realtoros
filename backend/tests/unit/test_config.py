"""Tests for configuration system.

SECRET_KEY and AI_CHATGPT_API_KEY are required fields.
Tests assume .env is properly configured with at least SECRET_KEY set.
"""

from backend.config import settings


def test_settings_loads():
    """Settings can be imported and has required attributes."""
    assert settings.APP_VERSION == "0.2.0"
    assert settings.APP_TITLE == "Real Estate OS API"


def test_database_settings():
    """Database group has all required fields with correct defaults."""
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert settings.DATABASE_SYNC_URL.startswith("postgresql://")
    assert settings.DB_POOL_SIZE == 5
    assert settings.DB_MAX_OVERFLOW == 10
    assert isinstance(settings.DB_ECHO, bool)


def test_app_settings():
    """App group has all required fields."""
    assert isinstance(settings.APP_HOST, str)
    assert isinstance(settings.APP_PORT, int)
    assert 1024 <= settings.APP_PORT <= 65535
    assert isinstance(settings.APP_DEBUG, bool)
    assert isinstance(settings.APP_TITLE, str)
    assert isinstance(settings.APP_VERSION, str)
    assert isinstance(settings.APP_DESCRIPTION, str)


def test_security_settings():
    """Security group: SECRET_KEY is required (no default)."""
    assert isinstance(settings.SECRET_KEY, str)
    assert len(settings.SECRET_KEY) > 0
    assert isinstance(settings.ACCESS_TOKEN_EXPIRE_MINUTES, int)
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
    assert settings.JWT_ALGORITHM in {"HS256", "HS384", "HS512", "RS256"}


def test_telegram_settings():
    """Telegram group has all required fields with empty defaults."""
    assert settings.TELEGRAM_BOT_TOKEN == ""
    assert settings.TELEGRAM_API_ID == 0
    assert settings.TELEGRAM_API_HASH == ""
    assert settings.REVIEW_GROUP_CHAT_ID == ""


def test_ai_settings():
    """AI models group: CHATGPT_API_KEY is required (no default)."""
    assert settings.AI_QWEN_ENDPOINT.startswith("http")
    assert isinstance(settings.AI_DEEPSEEK_FLASH, str)
    assert isinstance(settings.AI_DEEPSEEK_PRO, str)
    assert isinstance(settings.AI_CHATGPT_API_KEY, str)
    assert len(settings.AI_CHATGPT_API_KEY) > 0
    assert isinstance(settings.AI_EMBEDDING_MODEL, str)


def test_lead_scoring_settings():
    """Lead scoring group has all required fields with valid ranges."""
    assert 0.0 <= settings.LEAD_SCORE_RULE_HOT <= 1.0
    assert 0.0 <= settings.LEAD_SCORE_RULE_WARM <= 1.0
    assert 0.0 <= settings.LEAD_SCORE_RULE_COLD <= 1.0
    assert settings.LEAD_SCORE_RULE_HOT > settings.LEAD_SCORE_RULE_WARM > settings.LEAD_SCORE_RULE_COLD
    assert 0.0 <= settings.LEAD_AUTO_ASSIGN_THRESHOLD <= 1.0
    assert isinstance(settings.LEAD_EXPIRY_DAYS, int)
    assert settings.LEAD_EXPIRY_DAYS >= 1
    assert isinstance(settings.LEAD_MAX_REOPEN, int)
    assert settings.LEAD_MAX_REOPEN >= 1


def test_integration_settings():
    """Integrations group has all required fields with empty defaults."""
    assert isinstance(settings.AVITO_API_KEY, str)
    assert isinstance(settings.CIAN_API_KEY, str)


def test_seven_config_groups():
    """All 7 config groups are present."""
    groups = [
        "DATABASE_URL",         # Database
        "APP_TITLE",             # App
        "SECRET_KEY",            # Security
        "TELEGRAM_BOT_TOKEN",    # Telegram
        "AI_QWEN_ENDPOINT",      # AI Models
        "LEAD_SCORE_RULE_HOT",   # Lead Scoring
        "AVITO_API_KEY",         # Integrations
    ]
    for group in groups:
        assert hasattr(settings, group), f"Missing config: {group}"


def test_required_fields_have_no_default():
    """Required fields raise if env var is missing (compile-time check)."""
    # These fields have no default value — they MUST be in .env.
    # This test verifies they exist in the running settings instance.
    assert "SECRET_KEY" in settings.model_fields
    assert settings.model_fields["SECRET_KEY"].is_required()
    assert "AI_CHATGPT_API_KEY" in settings.model_fields
    assert settings.model_fields["AI_CHATGPT_API_KEY"].is_required()


def test_db_pool_sane_for_4gb():
    """Pool config suitable for 4 GB Ubuntu + PostgreSQL + FastAPI."""
    total_connections = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
    assert total_connections <= 20, "Too many connections for 4 GB server"
    assert settings.DB_POOL_SIZE >= 2, "Pool too small for concurrent requests"
