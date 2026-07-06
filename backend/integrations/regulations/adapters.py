"""Regulation source adapters — isolated implementations for each provider."""

from __future__ import annotations

from datetime import datetime, timezone

from structlog import get_logger

from backend.integrations.regulations.base_adapter import RegulationSourceAdapter, SourceFetchResult

logger = get_logger(__name__)


class RosreestrAdapter(RegulationSourceAdapter):
    """Адаптер для Росреестра.

    Источник: https://rosreestr.gov.ru
    Содержит: законы о регистрации недвижимости, выписки ЕГРН.
    """

    def __init__(self, base_url: str = "https://rosreestr.gov.ru"):
        self.base_url = base_url

    async def fetch_updates(self, since: str | None = None) -> SourceFetchResult:
        logger.info("rosreestr_fetch_updates", since=since)
        return SourceFetchResult(documents=[
            {
                "id": "218-fz",
                "title": "Федеральный закон №218-ФЗ «О госрегистрации недвижимости»",
                "version": "14.0",
                "effective_from": "2026-01-01",
                "category": "registration",
            }
        ])

    async def fetch_document(self, document_id: str) -> dict | None:
        return {
            "id": document_id,
            "title": f"Document {document_id} from Rosreestr",
            "content": f"Content placeholder for {document_id}",
        }

    async def get_metadata(self) -> dict:
        return {"source": "rosreestr", "status": "available", "documents_count": 150}


class FNSAdapter(RegulationSourceAdapter):
    """Адаптер для ФНС России.

    Источник: https://nalog.gov.ru
    Содержит: налоговые законы, имущественные вычеты.
    """

    def __init__(self, base_url: str = "https://nalog.gov.ru"):
        self.base_url = base_url

    async def fetch_updates(self, since: str | None = None) -> SourceFetchResult:
        logger.info("fns_fetch_updates", since=since)
        return SourceFetchResult(documents=[
            {
                "id": "nk-rf",
                "title": "Налоговый кодекс РФ — глава об имущественном налоге",
                "version": "5.0",
                "effective_from": "2026-03-01",
                "category": "taxation",
            }
        ])

    async def fetch_document(self, document_id: str) -> dict | None:
        return {"id": document_id, "title": f"FNS: {document_id}", "content": ""}

    async def get_metadata(self) -> dict:
        return {"source": "nalog", "status": "available"}


class CBRAdapter(RegulationSourceAdapter):
    """Адаптер для ЦБ РФ.

    Источник: https://cbr.ru
    Содержит: ипотечные законы, кредитные ставки, нормативы.
    """

    def __init__(self, base_url: str = "https://cbr.ru"):
        self.base_url = base_url

    async def fetch_updates(self, since: str | None = None) -> SourceFetchResult:
        logger.info("cbr_fetch_updates", since=since)
        return SourceFetchResult(documents=[
            {
                "id": "102-fz",
                "title": "Федеральный закон №102-ФЗ «Об ипотеке»",
                "version": "6.0",
                "effective_from": "2026-04-01",
                "category": "mortgage",
            }
        ])

    async def fetch_document(self, document_id: str) -> dict | None:
        return {"id": document_id, "title": f"CBR: {document_id}", "content": ""}

    async def get_metadata(self) -> dict:
        return {"source": "cbr", "status": "available"}


class GovernmentPortalAdapter(RegulationSourceAdapter):
    """Адаптер для Правительства РФ.

    Источник: https://government.ru
    Содержит: постановления, распоряжения, изменения в законах.
    """

    def __init__(self, base_url: str = "https://government.ru"):
        self.base_url = base_url

    async def fetch_updates(self, since: str | None = None) -> SourceFetchResult:
        logger.info("government_fetch_updates", since=since)
        return SourceFetchResult(documents=[])

    async def fetch_document(self, document_id: str) -> dict | None:
        return None

    async def get_metadata(self) -> dict:
        return {"source": "government", "status": "available"}


class ConsultantAdapter(RegulationSourceAdapter):
    """Адаптер для КонсультантПлюс."""

    def __init__(self, base_url: str = "https://consultant.ru"):
        self.base_url = base_url

    async def fetch_updates(self, since: str | None = None) -> SourceFetchResult:
        return SourceFetchResult(documents=[])

    async def fetch_document(self, document_id: str) -> dict | None:
        return None

    async def get_metadata(self) -> dict:
        return {"source": "consultant", "status": "available"}


class GarantAdapter(RegulationSourceAdapter):
    """Адаптер для Гарант."""

    def __init__(self, base_url: str = "https://garant.ru"):
        self.base_url = base_url

    async def fetch_updates(self, since: str | None = None) -> SourceFetchResult:
        return SourceFetchResult(documents=[])

    async def fetch_document(self, document_id: str) -> dict | None:
        return None

    async def get_metadata(self) -> dict:
        return {"source": "garant", "status": "available"}
