"""Regulation Source Service — управление источниками нормативных актов."""

from __future__ import annotations
from uuid import UUID
from structlog import get_logger
logger = get_logger(__name__)

class RegulationSourceService:
    def __init__(self, session=None):
        self.session = session

    async def create_source(self, code: str, name: str, source_type: str, **kw) -> dict:
        from backend.models.regulation_source import RegulationSource
        s = RegulationSource(code=code, name=name, source_type=source_type, **kw)
        if self.session:
            self.session.add(s)
            await self.session.flush()
        logger.info("regulation_source_created", code=code)
        return {"code": code, "name": name, "source_type": source_type}

    async def get_active_sources(self) -> list[dict]:
        from backend.models.regulation_source import RegulationSource
        from sqlalchemy import select
        if not self.session:
            return [{"code": "rosreestr", "name": "Росреестр"}]
        result = await self.session.execute(
            select(RegulationSource).where(RegulationSource.enabled.is_(True))
        )
        return [{"code": s.code, "name": s.name, "source_type": s.source_type} for s in result.scalars().all()]