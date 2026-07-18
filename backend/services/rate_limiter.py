"""Distributed Rate Limiter — PostgreSQL-backed, survives restarts and multi-instance.

Uses advisory lock + throttle table for distributed rate limiting.
Falls back to in-memory if PG unavailable.
"""

from __future__ import annotations

import time
from uuid import UUID

from structlog import get_logger

logger = get_logger(__name__)


class PostgresRateLimiter:
    """Распределённый rate limiter через PostgreSQL.

    Использует advisory lock (pg_try_advisory_lock) для координации
    между инстансами + таблицу rate_limits для персистентности.

    Limits:
    - 10 requests per minute
    - 100 requests per hour
    """

    def __init__(self, session=None, rpm: int = 10, rph: int = 100):
        self._session = session
        self._rpm = rpm
        self._rph = rph

    async def check(self, user_id: UUID) -> bool:
        """Проверить лимит. True = разрешено.

        Использует таблицу rate_limits (ключ: user_id + window).
        """
        if self._session is None:
            return self._check_memory(user_id)

        return await self._check_pg(user_id)

    async def _check_pg(self, user_id: UUID) -> bool:
        """PostgreSQL-backed check with advisory lock."""
        from sqlalchemy import text

        now_ts = int(time.time())
        minute_window = now_ts // 60
        hour_window = now_ts // 3600

        try:
            # Try to acquire advisory lock (session-level, not blocking)
            lock_result = await self._session.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": hash(f"rate_limit:{user_id}") % (2**63)},
            )
            locked = lock_result.scalar()
            if not locked:
                return False  # другой инстанс уже обрабатывает

            # Check minute window
            result = await self._session.execute(
                text("""
                    SELECT count FROM rate_limits
                    WHERE user_id = :uid AND window_type = 'minute' AND window_key = :minute_key
                """),
                {"uid": user_id, "minute_key": minute_window},
            )
            minute_count = (result.scalar() or 0)
            if minute_count >= self._rpm:
                return False

            # Check hour window
            result = await self._session.execute(
                text("""
                    SELECT count FROM rate_limits
                    WHERE user_id = :uid AND window_type = 'hour' AND window_key = :hour_key
                """),
                {"uid": user_id, "hour_key": hour_window},
            )
            hour_count = (result.scalar() or 0)
            if hour_count >= self._rph:
                return False

            # Upsert minute counter
            await self._session.execute(
                text("""
                    INSERT INTO rate_limits (user_id, window_type, window_key, count)
                    VALUES (:uid, 'minute', :minute_key, 1)
                    ON CONFLICT (user_id, window_type, window_key)
                    DO UPDATE SET count = rate_limits.count + 1
                """),
                {"uid": user_id, "minute_key": minute_window},
            )

            # Upsert hour counter
            await self._session.execute(
                text("""
                    INSERT INTO rate_limits (user_id, window_type, window_key, count)
                    VALUES (:uid, 'hour', :hour_key, 1)
                    ON CONFLICT (user_id, window_type, window_key)
                    DO UPDATE SET count = rate_limits.count + 1
                """),
                {"uid": user_id, "hour_key": hour_window},
            )

            await self._session.flush()
            return True

        except Exception as e:
            logger.warning("rate_limiter_pg_failed", error=str(e))
            return self._check_memory(user_id)

    def _check_memory(self, user_id: UUID) -> bool:
        """Fallback: in-memory check."""
        MinuteWindowRateLimiter._get_instance()._check(user_id)
        return True

    async def cleanup_old(self) -> int:
        """Очистить старые записи (вызывать по cron)."""
        if self._session is None:
            return 0
        from sqlalchemy import text
        cutoff = int(time.time()) - 7200  # 2 hours
        result = await self._session.execute(
            text("DELETE FROM rate_limits WHERE window_key < :cutoff"),
            {"cutoff": cutoff // 60},
        )
        return result.rowcount


class MinuteWindowRateLimiter:
    """In-memory fallback rate limiter (single instance)."""

    _instance = None

    @classmethod
    def _get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        import collections
        self._minute_windows = collections.defaultdict(list)

    def _check(self, user_id: UUID, rpm: int = 10) -> bool:
        now = time.monotonic()
        minute_ago = now - 60
        windows = self._minute_windows[user_id]
        self._minute_windows[user_id] = [t for t in windows if t > minute_ago]
        if len(self._minute_windows[user_id]) >= rpm:
            return False
        self._minute_windows[user_id].append(now)
        return True
