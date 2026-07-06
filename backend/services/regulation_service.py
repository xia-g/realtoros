"""RegulationService — поиск и получение нормативных актов."""

from __future__ import annotations

from uuid import UUID

from structlog import get_logger

logger = get_logger(__name__)


class RegulationService:
    """Сервис для работы с нормативными актами.

    Trust levels:
        OFFICIAL — официальный текст (Минфин, ФНС, Росреестр, ЦБ)
        VERIFIED — проверенный источник (Госуслуги, нотариусы)
        COMMUNITY — сообщество (риелторские ассоциации)
        LLM_GENERATED — сгенерировано LLM (требует проверки)
    """

    TRUST_LEVELS = ["OFFICIAL", "VERIFIED", "COMMUNITY", "LLM_GENERATED"]

    def __init__(self, regulation_repo=None):
        self._repo = regulation_repo

    async def search_regulations(
        self,
        query: str,
        min_trust: str = "COMMUNITY",
        limit: int = 10,
    ) -> list[dict]:
        """Поиск нормативных актов с фильтром по уровню доверия."""
        if self._repo is None:
            return await self._search_local(query, min_trust, limit)

        results = await self._repo.search(query, limit=limit)
        return [
            {
                "id": str(r.id),
                "title": r.title,
                "source": r.source,
                "trust_level": r.trust_level,
                "version": r.version,
                "effective_from": str(r.effective_from),
                "effective_to": str(r.effective_to) if r.effective_to else None,
                "url": r.url,
                "category": r.category,
                "tags": r.tags or [],
            }
            for r in results
            if self._trust_level_value(r.trust_level) >= self._trust_level_value(min_trust)
        ]

    async def get_regulation(self, regulation_id: UUID | str) -> dict | None:
        """Получить нормативный акт по ID."""
        if isinstance(regulation_id, str):
            regulation_id = UUID(regulation_id)

        if self._repo is None:
            return {"error": "Regulation repository not configured"}

        result = await self._repo.get_by_id(regulation_id)
        if result is None or result.deleted_at is not None:
            return None

        return {
            "id": str(result.id),
            "title": result.title,
            "source": result.source,
            "trust_level": result.trust_level,
            "version": result.version,
            "effective_from": str(result.effective_from),
            "effective_to": str(result.effective_to) if result.effective_to else None,
            "url": result.url,
            "content": result.content[:2000] if result.content else None,
            "category": result.category,
            "tags": result.tags or [],
        }

    async def _search_local(self, query: str, min_trust: str, limit: int) -> list[dict]:
        """Локальный fallback для тестов/демо."""
        import hashlib
        from datetime import date

        # Демо-данные для быстрой проверки
        demo = [
            {
                "title": "Федеральный закон №218-ФЗ «О госрегистрации недвижимости»",
                "source": "Росреестр",
                "trust_level": "OFFICIAL",
                "version": "1.0",
                "effective_from": "2025-01-01",
                "effective_to": None,
                "url": "https://rosreestr.gov.ru/docs/218-fz",
                "category": "registration",
                "tags": ["egrn", "registration", "real_estate"],
            },
            {
                "title": "Федеральный закон №214-ФЗ «Об участии в долевом строительстве»",
                "source": "Минфин",
                "trust_level": "OFFICIAL",
                "version": "2.0",
                "effective_from": "2025-06-01",
                "effective_to": None,
                "url": "https://minfin.gov.ru/docs/214-fz",
                "category": "construction",
                "tags": ["ddu", "construction", "shared"],
            },
            {
                "title": "Федеральный закон №102-ФЗ «Об ипотеке»",
                "source": "ЦБ",
                "trust_level": "OFFICIAL",
                "version": "1.1",
                "effective_from": "2024-01-01",
                "effective_to": "2026-12-31",
                "url": "https://cbr.ru/docs/102-fz",
                "category": "mortgage",
                "tags": ["mortgage", "lending"],
            },
        ]

        filtered = []
        for r in demo:
            if self._trust_level_value(r["trust_level"]) < self._trust_level_value(min_trust):
                continue
            if query.lower() in r["title"].lower() or any(query.lower() in t.lower() for t in r["tags"]):
                filtered.append(r)

        return filtered[:limit]

    @staticmethod
    def _trust_level_value(level: str) -> int:
        return {"OFFICIAL": 4, "VERIFIED": 3, "COMMUNITY": 2, "LLM_GENERATED": 1}.get(level, 0)
