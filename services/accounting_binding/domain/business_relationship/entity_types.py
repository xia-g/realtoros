"""
Entity types and identifier types for Business Relationship Engine.

NOT persistent — in-memory foundation for v2.0.1.
"""
from __future__ import annotations

from enum import Enum


class EntityType(str, Enum):
    PERSON = "person"
    COMPANY = "company"
    PROPERTY = "property"
    DOCUMENT = "document"          # extracted as entity, NOT agreement
    BANK = "bank"
    GOVERNMENT = "government"
    AGREEMENT = "agreement"        # reserved for v2.0.2 AgreementResolver


class IdentifierType(str, Enum):
    INN = "inn"
    OGRN = "ogrn"
    KPP = "kpp"
    CADASTRE = "cadastre"
    EMAIL = "email"
    PHONE = "phone"
    BANK_ACCOUNT = "bank_account"
    BIK = "bik"
    ADDRESS = "address"
    CONTRACT_NUMBER = "contract_number"
