"""
Domain — Enrichment.

Преобразует OCR-данные (NormalizedDocument) в бизнес-контекст:
canonical entities, counterparty discovery, нормализация.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol

from contracts import NormalizedDocument, EnrichedDocument, CounterpartyInfo
from domain.enrichment.party_identity import MasterDataStore
from domain.enrichment.party_classifier import PartyClassifier


class CounterpartyResolver(Protocol):
    """Интерфейс для поиска контрагента по ИНН/названию."""
    async def resolve(self, name: str, inn: str | None = None) -> CounterpartyInfo: ...


class DedupService(Protocol):
    """Интерфейс для проверки дубликатов."""
    async def check(self, doc_hash: str) -> list[str]: ...


@dataclass
class EnrichmentResult:
    """Результат обогащения."""
    enriched: EnrichedDocument
    warnings: list[str] = field(default_factory=list)


class DocumentEnricher:
    """Обогащение документа: нормализация сущностей + контрагент."""

    def __init__(
        self,
        counterparty_resolver: CounterpartyResolver | None = None,
        dedup_service: DedupService | None = None,
        master_data: MasterDataStore | None = None,
    ):
        self._resolver = counterparty_resolver
        self._dedup = dedup_service
        self._party_classifier = PartyClassifier(master_data)

    async def enrich(self, doc: NormalizedDocument) -> EnrichmentResult:
        """Запустить полный цикл обогащения."""
        warnings: list[str] = []
        dedup_ids: list[str] = []

        # 1. Нормализация сумм
        canonical_amounts = self._normalize_amounts(doc.entities.amount)
        if not canonical_amounts and doc.entities.amount:
            warnings.append("Некоторые суммы не удалось нормализовать")

        # 2. Нормализация дат
        canonical_dates = self._normalize_dates(doc.entities.date)
        if not canonical_dates and doc.entities.date:
            warnings.append("Некоторые даты не удалось нормализовать")

        # 3. Контрагент
        counterparty = CounterpartyInfo()
        if self._resolver:
            company_name = doc.entities.company[0] if doc.entities.company else ""
            inn = doc.entities.vat_number[0] if doc.entities.vat_number else None
            counterparty = await self._resolver.resolve(company_name, inn)
            if counterparty.status == "unknown":
                warnings.append("Контрагент не найден")

        # 4. Party Identity Resolution (v1.5.1)
        parties: list[dict] = []
        transaction_tags: list[str] = []
        classification_hash: str = ""
        if self._party_classifier:
            result = await self._party_classifier.classify(
                company_names=doc.entities.company,
                person_names=doc.entities.persons,
                counterparty_inn=doc.entities.vat_number[0] if doc.entities.vat_number else "",
                company_id=counterparty.canonical_id or "",
            )
            parties = [
                {"identity": {
                    "name": p.identity.name,
                    "entity_type": p.identity.entity_type.value,
                    "business_status": p.identity.business_status.value,
                    "confidence": p.identity.confidence,
                    "source": p.identity.source.value if hasattr(p.identity.source, "value") else str(p.identity.source),
                }, "relation": {
                    "role": p.relation.role.value,
                    "relation": p.relation.relation.value,
                    "confidence": p.relation.confidence,
                }}
                for p in result.parties
            ]
            transaction_tags = result.tags
            classification_hash = result.classification_hash
            warnings.extend(result.warnings)

        # 5. Дедупликация
        dedup_hash = self._compute_hash(doc)
        if self._dedup:
            dedup_ids = await self._dedup.check(dedup_hash)

        enriched = EnrichedDocument(
            document_id=doc.document_id,
            trace_id=doc.trace_id,
            source=doc.source,
            document_type=doc.document_type,
            counterparty=counterparty,
            parties=parties,
            transaction_tags=transaction_tags,
            classification_hash=classification_hash,
            canonical_amounts=canonical_amounts,
            canonical_dates=canonical_dates,
            document_number=doc.entities.document_number[0] if doc.entities.document_number else "",
            vat_numbers=doc.entities.vat_number,
            ibans=doc.entities.iban,
            addresses=doc.entities.addresses,
            persons=doc.entities.persons,
            enrichment_confidence=doc.confidence.overall_confidence,
            enrichment_warnings=warnings,
            dedup_hash=dedup_hash,
            dedup_source_ids=dedup_ids,
            source_document=doc,
        )
        return EnrichmentResult(enriched, warnings)

    def _normalize_amounts(self, raw_amounts: list[float]) -> list:
        """Нормализовать суммы: float → Decimal."""
        from contracts import CanonicalAmount
        result = []
        for val in raw_amounts:
            try:
                dec = Decimal(str(val)).quantize(Decimal("0.01"))
                result.append(CanonicalAmount(
                    raw_text=str(val), amount=dec, currency="RUB", confidence=0.9
                ))
            except (InvalidOperation, ValueError):
                pass
        return result

    def _normalize_dates(self, raw_dates: list[str]) -> list:
        """Нормализовать даты: строка → date."""
        from datetime import datetime as dt
        from contracts import CanonicalDate
        result = []
        for raw in raw_dates:
            for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    parsed = dt.strptime(raw.strip(), fmt).date()
                    result.append(CanonicalDate(
                        raw_text=raw, parsed_date=parsed, confidence=0.95
                    ))
                    break
                except ValueError:
                    continue
        return result

    def _compute_hash(self, doc: NormalizedDocument) -> str:
        """Вычислить хеш для дедупликации."""
        import hashlib
        raw = f"{doc.source}:{doc.document_type}:{doc.raw_text[:100]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
