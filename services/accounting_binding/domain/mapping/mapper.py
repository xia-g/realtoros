"""
Domain — Accounting Mapping.

enriched_document → accounting_document:
- account resolution
- tax mapping
- dimensions
- posting preparation

Идемпотентно: одинаковый enriched_document → одинаковый accounting_document.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from contracts import (
    EnrichedDocument,
    AccountingDocument,
    AccountEntry,
    AccountingSide,
    TaxEntry,
    DocumentType,
)
from domain.hash import canonical_hash


class AccountBook(Protocol):
    """Интерфейс плана счетов."""
    async def resolve(self, doc_type: DocumentType, counterparty_inn: str) -> list[AccountEntry]: ...


class TaxMappingService(Protocol):
    """Интерфейс налогового маппинга."""
    async def resolve(self, doc_type: DocumentType, amount: Decimal) -> list[TaxEntry]: ...


@dataclass
class MappingResult:
    """Результат маппинга."""
    accounting_document: AccountingDocument
    warnings: list[str]


class AccountingMapper:
    """Маппинг enriched_document → accounting_document."""

    def __init__(
        self,
        account_book: AccountBook | None = None,
        tax_mapping: TaxMappingService | None = None,
    ):
        self._account_book = account_book
        self._tax_mapping = tax_mapping

    async def map(self, doc: EnrichedDocument) -> MappingResult:
        """Преобразовать enriched_document в accounting_document."""
        warnings: list[str] = []

        # 1. Определяем основную сумму
        main_amount = Decimal("0")
        if doc.canonical_amounts:
            main_amount = doc.canonical_amounts[0].amount

        # 2. Определяем дату документа
        doc_date = doc.canonical_dates[0].parsed_date if doc.canonical_dates else None
        if doc_date is None and doc.source_document:
            doc_date = doc.source_document.metadata.get("upload_date")
        if doc_date is None:
            from datetime import date
            doc_date = date.today()
            warnings.append("Дата документа не распознана, используется today")

        # 3. Разрешаем счета
        entries: list[AccountEntry] = []
        if self._account_book:
            entries = await self._account_book.resolve(doc.document_type, doc.counterparty_inn)
        if not entries:
            entries = self._default_entries(doc.document_type, main_amount, doc)

        # 4. Налоговый маппинг
        tax_entries: list[TaxEntry] = []
        if self._tax_mapping:
            tax_entries = await self._tax_mapping.resolve(doc.document_type, main_amount)

        # 5. Итоги
        total_debit = sum((e.amount for e in entries if e.side == AccountingSide.DEBIT), Decimal("0"))
        total_credit = sum((e.amount for e in entries if e.side == AccountingSide.CREDIT), Decimal("0"))

        # 6. Хеш идемпотентности
        mapping_hash = self._compute_hash(doc, entries, tax_entries)

        accounting = AccountingDocument(
            document_id=doc.document_id,
            trace_id=doc.trace_id,
            source=doc.source,
            document_type=doc.document_type,
            enriched_document_id=doc.document_id,
            company_id="",
            document_date=doc_date,
            entries=entries,
            tax_entries=tax_entries,
            total_debit=total_debit,
            total_credit=total_credit,
            mapping_hash=mapping_hash,
        )
        return MappingResult(accounting, warnings)

    def _default_entries(
        self, doc_type: DocumentType, amount: Decimal, doc: EnrichedDocument
    ) -> list[AccountEntry]:
        """Типовые проводки по типу документа.

        В продакшене заменяется AccountBook.resolve().
        """
        if amount == Decimal("0"):
            return []

        if doc_type == DocumentType.INVOICE:
            # Дт 19 (НДС) / Кт 60.01 (поставщик)
            vat = amount * Decimal("20") / Decimal("120")
            base = amount - vat
            return [
                AccountEntry(account_code="08", side=AccountingSide.DEBIT, amount=base, sequence=0),
                AccountEntry(account_code="19", side=AccountingSide.DEBIT, amount=vat, sequence=1),
                AccountEntry(account_code="60.01", side=AccountingSide.CREDIT, amount=amount, sequence=2),
            ]
        elif doc_type == DocumentType.CONTRACT:
            # Дт 08 / Кт 60.01
            return [
                AccountEntry(account_code="08", side=AccountingSide.DEBIT, amount=amount, sequence=0),
                AccountEntry(account_code="60.01", side=AccountingSide.CREDIT, amount=amount, sequence=1),
            ]
        elif doc_type == DocumentType.RECEIPT:
            return [
                AccountEntry(account_code="26", side=AccountingSide.DEBIT, amount=amount, sequence=0),
                AccountEntry(account_code="71", side=AccountingSide.CREDIT, amount=amount, sequence=1),
            ]
        else:
            return [
                AccountEntry(account_code="76", side=AccountingSide.DEBIT, amount=amount, sequence=0),
                AccountEntry(account_code="76", side=AccountingSide.CREDIT, amount=amount, sequence=1),
            ]

    def _compute_hash(
        self, doc: EnrichedDocument, entries: list[AccountEntry], tax: list[TaxEntry]
    ) -> str:
        """Canonical hash. Не включает id/timestamp."""
        payload = {
            "doc_type": doc.document_type.value if hasattr(doc.document_type, "value") else doc.document_type,
            "counterparty_inn": doc.counterparty_inn,
            "entries": [
                {"account_code": e.account_code, "side": e.side.value if hasattr(e.side, "value") else e.side,
                 "amount": str(e.amount), "dimension": e.dimension}
                for e in entries
            ],
            "tax": [
                {"tax_code": t.tax_code, "tax_rate": str(t.tax_rate),
                 "taxable_amount": str(t.taxable_amount), "tax_amount": str(t.tax_amount)}
                for t in tax
            ],
        }
        return canonical_hash(payload)
