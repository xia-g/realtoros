"""
DocumentReference — ссылка между документами.

Например: "Акт к договору №2182" → appendix_to

NO DB writes. Immutable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from domain.business_relationship.provenance import Provenance, DocumentRevision


class ReferenceType(str, Enum):
    REFERS_TO = "refers_to"            # ссылается на
    APPENDIX_TO = "appendix_to"        # приложение к
    AMENDMENT_TO = "amendment_to"      # изменение к
    EXECUTES = "executes"              # исполняет
    PAYS_FOR = "pays_for"              # оплачивает
    INVOICE_FOR = "invoice_for"        # счёт для
    ACT_FOR = "act_for"                # акт к


@dataclass(frozen=True)
class DocumentReference:
    """Ссылка между документами. Immutable."""
    reference_type: ReferenceType
    source_document_id: str
    target_document_identifier: str    # номер или идентификатор целевого документа
    provenance: Provenance
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confidence: float = 0.85
