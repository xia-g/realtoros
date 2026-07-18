"""Entity extraction from document text.

Uses LLM (DeepSeek Flash/Pro, GPT-4o fallback) to extract structured entities.
Outputs strict JSON schema per entity type.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from backend.core.logging import get_logger

logger = get_logger("knowledge")


@dataclass
class ExtractedEntities:
    persons: list[dict] = field(default_factory=list)
    properties: list[dict] = field(default_factory=list)
    deals: list[dict] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)
    organizations: list[dict] = field(default_factory=list)
    raw: dict | None = None


PERSON_PATTERN = re.compile(
    r"(?P<full_name>[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+)"
)
PHONE_PATTERN = re.compile(r"\+?7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
CADASTRAL_PATTERN = re.compile(r"\d{2}:\d{2}:\d{7}:\d{3}")
INN_PATTERN = re.compile(r"\d{10}")
OGRN_PATTERN = re.compile(r"\d{13}")
AMOUNT_PATTERN = re.compile(r"(?P<amount>\d[\d\s]*)\s*(?:руб|₽|тыс|миллион|млн)")


class EntityExtractionService:
    """Extract structured entities from document text using patterns + LLM."""

    def __init__(self):
        self._llm_available = False

    async def extract(self, text: str, doc_type: str = "unknown") -> ExtractedEntities:
        result = ExtractedEntities()
        self._extract_patterns(text, result)

        if doc_type in ("passport", "egrn", "contract"):
            await self._enhance_with_llm(text, result, doc_type)

        logger.info(
            "extraction_completed",
            doc_type=doc_type,
            persons=len(result.persons),
            properties=len(result.properties),
        )
        return result

    def _extract_patterns(self, text: str, result: ExtractedEntities) -> None:
        seen_phones = set()
        seen_emails = set()

        for match in PERSON_PATTERN.finditer(text):
            name = match.group("full_name")
            result.persons.append({
                "full_name": name.strip(),
                "phone": "",
                "email": "",
                "source": "pattern",
                "confidence": 0.6,
            })

        for phone in PHONE_PATTERN.findall(text):
            clean = phone.strip()
            if clean not in seen_phones:
                seen_phones.add(clean)
                if result.persons:
                    result.persons[-1]["phone"] = clean
                else:
                    result.persons.append({
                        "full_name": "", "phone": clean, "email": "",
                        "source": "pattern", "confidence": 0.5,
                    })

        for email in EMAIL_PATTERN.findall(text):
            clean = email.strip()
            if clean not in seen_emails:
                seen_emails.add(clean)
                if result.persons:
                    result.persons[-1]["email"] = clean

        for cad in CADASTRAL_PATTERN.findall(text):
            result.properties.append({
                "cadastral_number": cad.strip(),
                "address": "",
                "source": "pattern",
                "confidence": 0.8,
            })

        for inn in INN_PATTERN.findall(text):
            result.organizations.append({
                "name": "", "inn": inn, "ogrn": "",
                "source": "pattern", "confidence": 0.7,
            })

        for ogrn in OGRN_PATTERN.findall(text):
            if result.organizations:
                result.organizations[-1]["ogrn"] = ogrn

        from backend.models.document import Document

    async def _enhance_with_llm(self, text: str, result: ExtractedEntities, doc_type: str) -> None:
        """Use LLM to extract entities from structured documents."""
        try:
            prompt = self._build_prompt(text, doc_type)
            llm_result = await self._call_llm(prompt)
            if llm_result:
                if "persons" in llm_result:
                    result.persons.extend(llm_result["persons"])
                if "properties" in llm_result:
                    result.properties.extend(llm_result["properties"])
                if "deals" in llm_result:
                    result.deals.extend(llm_result["deals"])
                if "documents" in llm_result:
                    result.documents.extend(llm_result["documents"])
                result.raw = llm_result
        except Exception as e:
            logger.warning("llm_extraction_failed", error=str(e))

    def _build_prompt(self, text: str, doc_type: str) -> str:
        return (
            f"Extract entities from a {doc_type} document. "
            f"Return JSON with: persons, properties, deals, documents, organizations. "
            f"Text: {text[:3000]}"
        )

    async def _call_llm(self, prompt: str) -> dict | None:
        if not self._llm_available:
            return None
        # Stub — LLM integration will be added in Sprint 4
        return None