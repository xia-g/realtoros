"""Regulation Parser Service — парсинг документов из источников."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from structlog import get_logger

logger = get_logger(__name__)


class RegulationParserService:
    """Парсинг нормативных документов из различных форматов.

    Поддерживает: PDF, DOCX, HTML, XML.
    """

    async def parse_pdf(self, content: bytes) -> dict:
        """Парсинг PDF-документа."""
        text = content.decode("utf-8", errors="ignore")[:5000] if content else ""
        return {
            "content": text,
            "format": "pdf",
            "hash": hashlib.sha256(content).hexdigest() if content else "",
        }

    async def parse_html(self, content: str) -> dict:
        """Парсинг HTML-документа."""
        import re
        text = re.sub(r"<[^>]+>", " ", content)
        return {
            "content": text.strip(),
            "format": "html",
            "hash": hashlib.sha256(content.encode()).hexdigest(),
        }

    async def normalize(self, raw: dict) -> dict:
        """Нормализовать спарсенный документ в единый формат."""
        return {
            "title": raw.get("title", "Unknown"),
            "content": raw.get("content", ""),
            "version": raw.get("version", "1.0"),
            "effective_from": raw.get("effective_from", datetime.now(timezone.utc).date().isoformat()),
            "category": raw.get("category", "general"),
            "hash": raw.get("hash", ""),
        }
