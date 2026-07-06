"""
Mapper — AccountingDocument Domain ↔ Record.

Domain (frozen Pydantic) ↔ Mapper ↔ Record (SQLAlchemy).
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from contracts import AccountingDocument, AccountEntry, DocumentType, TaxEntry
from infrastructure.models.accounting_document_record import (
    AccountingDocumentRecord,
)


class AccountingDocumentMapper:
    """Преобразование между domain-моделью и ORM-записью."""

    @staticmethod
    def domain_to_record(doc: AccountingDocument) -> AccountingDocumentRecord:
        """Domain → ORM."""
        return AccountingDocumentRecord(
            id=doc.document_id,
            company_id=doc.company_id,
            document_date=doc.document_date,
            document_type=doc.document_type.value if hasattr(doc.document_type, "value") else doc.document_type,
            source=doc.source,
            trace_id=doc.trace_id,
            status=doc.status,
            process_state=doc.process_state,
            approval_required=doc.approval_required,
            entries_json=json.dumps(
                [e.model_dump(mode="json") for e in doc.entries],
                ensure_ascii=False, default=str,
            ),
            tax_entries_json=json.dumps(
                [t.model_dump(mode="json") for t in doc.tax_entries],
                ensure_ascii=False, default=str,
            ),
            total_debit=doc.total_debit,
            total_credit=doc.total_credit,
            mapping_hash=doc.mapping_hash,
            approval_revision=doc.approval_revision,
            approved_mapping_hash=doc.approved_mapping_hash,
        )

    @staticmethod
    def record_to_domain(record: AccountingDocumentRecord) -> AccountingDocument:
        """ORM → Domain."""
        entries_data = json.loads(record.entries_json or "[]")
        tax_data = json.loads(record.tax_entries_json or "[]")

        try:
            doc_type = DocumentType(record.document_type)
        except ValueError:
            doc_type = DocumentType.UNKNOWN

        return AccountingDocument(
            document_id=record.id,
            company_id=record.company_id,
            document_date=record.document_date,
            document_type=doc_type,
            source=record.source or "",
            trace_id=record.trace_id or "",
            status=record.status,
            process_state=record.process_state,
            approval_required=record.approval_required,
            entries=[AccountEntry(**e) for e in entries_data],
            tax_entries=[TaxEntry(**t) for t in tax_data],
            total_debit=record.total_debit,
            total_credit=record.total_credit,
            mapping_hash=record.mapping_hash or "",
            approval_revision=record.approval_revision or 0,
            approved_mapping_hash=record.approved_mapping_hash or "",
        )
