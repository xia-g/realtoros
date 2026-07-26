"""Contract Profile domain models for extraction v2.

Each section is a standalone dataclass.
ContractProfile aggregates all sections.
All fields are optional (None = not extracted).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any


# ─── Enums ────────────────────────────────────────────────────


class PartyType(str, Enum):
    LEGAL = "legal"
    INDIVIDUAL = "individual"


class PropertyType(str, Enum):
    NON_RESIDENTIAL = "non_residential"
    RESIDENTIAL = "residential"
    LAND = "land"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ─── Value Objects ──────────────────────────────────────────────


@dataclass
class ExtractedField:
    """A single extracted field with confidence."""
    value: Any
    confidence: float = 1.0
    raw: str = ""


@dataclass
class Money:
    value: Decimal
    currency: str = "RUB"


@dataclass
class ExtractionWarning:
    field: str
    code: str
    message: str
    severity: Severity = Severity.WARNING


# ─── Sections ─────────────────────────────────────────────────


@dataclass
class IdentificationSection:
    contract_number: ExtractedField | None = None
    contract_date: ExtractedField | None = None
    place_of_signing: ExtractedField | None = None

    @property
    def confidence(self) -> float:
        vals = [f for f in (self.contract_number, self.contract_date) if f]
        return sum(v.confidence for v in vals) / len(vals) if vals else 0.0


@dataclass
class Party:
    name: ExtractedField | None = None
    party_type: ExtractedField | None = None
    inn: ExtractedField | None = None
    kpp: ExtractedField | None = None
    ogrn: ExtractedField | None = None
    address: ExtractedField | None = None

    @property
    def confidence(self) -> float:
        vals = [f for f in (self.name, self.inn) if f]
        return sum(v.confidence for v in vals) / len(vals) if vals else 0.0


@dataclass
class PartiesSection:
    seller: Party = field(default_factory=Party)
    buyer: Party = field(default_factory=Party)

    @property
    def confidence(self) -> float:
        return (self.seller.confidence + self.buyer.confidence) / 2


@dataclass
class FinancialTermsSection:
    total_price: ExtractedField | None = None
    vat_amount: ExtractedField | None = None
    price_excluding_vat: ExtractedField | None = None
    deposit_amount: ExtractedField | None = None
    currency: ExtractedField | None = None

    @property
    def confidence(self) -> float:
        vals = [f for f in (self.total_price, self.vat_amount) if f]
        return sum(v.confidence for v in vals) / len(vals) if vals else 0.0


@dataclass
class PropertySection:
    address: ExtractedField | None = None
    area_sqm: ExtractedField | None = None
    floor: ExtractedField | None = None
    cadastral_number: ExtractedField | None = None
    property_type: ExtractedField | None = None

    @property
    def confidence(self) -> float:
        vals = [f for f in (self.cadastral_number, self.address) if f]
        return sum(v.confidence for v in vals) / len(vals) if vals else 0.0


@dataclass
class DatesSection:
    signing_date: ExtractedField | None = None
    payment_deadline: ExtractedField | None = None
    transfer_deadline: ExtractedField | None = None

    @property
    def confidence(self) -> float:
        vals = [f for f in (self.signing_date,) if f]
        return sum(v.confidence for v in vals) / len(vals) if vals else 0.0


@dataclass
class ReferenceSection:
    protocol_number: ExtractedField | None = None
    protocol_date: ExtractedField | None = None
    tender_number: ExtractedField | None = None

    @property
    def confidence(self) -> float:
        vals = [f for f in (self.tender_number,) if f]
        return sum(v.confidence for v in vals) / len(vals) if vals else 0.0


# ─── Metadata ─────────────────────────────────────────────────


@dataclass
class ExtractionMetadata:
    extracted_by: str = "pipeline:extraction-v2"
    confidence_per_field: dict[str, float] = field(default_factory=dict)
    warnings: list[ExtractionWarning] = field(default_factory=list)
    extraction_time_ms: int = 0

    def add_warning(self, field: str, code: str, msg: str, severity: Severity = Severity.WARNING):
        self.warnings.append(ExtractionWarning(field=field, code=code, message=msg, severity=severity))


# ─── Profile ──────────────────────────────────────────────────


@dataclass
class ContractProfile:
    """Structured contract document profile.

    All sections are independent. Each section has its own confidence.
    Profile confidence = average of section confidences.
    """
    identification: IdentificationSection = field(default_factory=IdentificationSection)
    parties: PartiesSection = field(default_factory=PartiesSection)
    financial_terms: FinancialTermsSection = field(default_factory=FinancialTermsSection)
    prop: PropertySection = field(default_factory=PropertySection)
    dates: DatesSection = field(default_factory=DatesSection)
    references: ReferenceSection = field(default_factory=ReferenceSection)
    metadata: ExtractionMetadata = field(default_factory=ExtractionMetadata)

    @property
    def confidence(self) -> float:
        sections = [
            self.identification, self.parties, self.financial_terms,
            self.prop, self.dates, self.references,
        ]
        vals = [s.confidence for s in sections if s.confidence > 0]
        return sum(vals) / len(vals) if vals else 0.0

    def to_dict(self) -> dict:
        """Serialise to nested dict for JSONB storage."""
        return {
            "profile_version": "1.0",
            "confidence": self.confidence,
            "sections": {
                "identification": {
                    "contract_number": _fv(self.identification.contract_number),
                    "contract_date": _fd(self.identification.contract_date),
                    "place_of_signing": _fv(self.identification.place_of_signing),
                },
                "parties": {
                    "seller": {
                        "name": _fv(self.parties.seller.name),
                        "type": _fv(self.parties.seller.party_type),
                        "inn": _fv(self.parties.seller.inn),
                        "kpp": _fv(self.parties.seller.kpp),
                        "ogrn": _fv(self.parties.seller.ogrn),
                    },
                    "buyer": {
                        "name": _fv(self.parties.buyer.name),
                        "type": _fv(self.parties.buyer.party_type),
                        "inn": _fv(self.parties.buyer.inn),
                        "kpp": _fv(self.parties.buyer.kpp),
                        "ogrn": _fv(self.parties.buyer.ogrn),
                    },
                },
                "financial_terms": {
                    "total_price": _fm(self.financial_terms.total_price),
                    "vat_amount": _fm(self.financial_terms.vat_amount),
                    "price_excluding_vat": _fm(self.financial_terms.price_excluding_vat),
                    "deposit_amount": _fm(self.financial_terms.deposit_amount),
                    "currency": _fv(self.financial_terms.currency),
                },
                "property": {
                    "address": _fv(self.prop.address),
                    "area_sqm": _fv(self.prop.area_sqm),
                    "floor": _fv(self.prop.floor),
                    "cadastral_number": _fv(self.prop.cadastral_number),
                    "property_type": _fv(self.prop.property_type),
                },
                "dates": {
                    "signing_date": _fd(self.dates.signing_date),
                    "payment_deadline": _fd(self.dates.payment_deadline),
                    "transfer_deadline": _fd(self.dates.transfer_deadline),
                },
                "references": {
                    "protocol_number": _fv(self.references.protocol_number),
                    "protocol_date": _fd(self.references.protocol_date),
                    "tender_number": _fv(self.references.tender_number),
                },
            },
            "metadata": {
                "extracted_by": self.metadata.extracted_by,
                "confidence_per_field": self.metadata.confidence_per_field,
                "warnings": [
                    {"field": w.field, "code": w.code, "message": w.message, "severity": w.severity.value}
                    for w in self.metadata.warnings
                ],
            },
        }


# ─── Serialisation helpers ────────────────────────────────────


def _fv(field: ExtractedField | None) -> str | float | None:
    return field.value if field else None


def _fd(field: ExtractedField | None) -> str | None:
    if field and field.value:
        if isinstance(field.value, date):
            return field.value.isoformat()
        return str(field.value)
    return None


def _fm(field: ExtractedField | None) -> dict | None:
    if field and field.value:
        if isinstance(field.value, Money):
            return {"value": float(field.value.value), "currency": field.value.currency}
        return {"value": float(field.value), "currency": "RUB"}
    return None
