"""
Neutral fact types for v2.0.1a.

Facts describe OBSERVABLE content of a document.
NO business interpretation (SELLS, OWNS, BUYS, etc. → v2.0.2).

Every fact describes what was ACTUALLY found in the document.
"""
from __future__ import annotations

from enum import Enum


class FactType(str, Enum):
    # Document structure
    DOCUMENT_HAS_PARTY = "document_has_party"                # у документа есть сторона
    DOCUMENT_HAS_PROPERTY = "document_has_property"          # документ ссылается на объект недвижимости
    DOCUMENT_HAS_AMOUNT = "document_has_amount"              # в документе указана сумма
    DOCUMENT_HAS_DATE = "document_has_date"                  # у документа есть дата
    DOCUMENT_HAS_IDENTIFIER = "document_has_identifier"      # у документа есть идентификатор (ИНН)
    DOCUMENT_HAS_SIGNATURE = "document_has_signature"        # документ подписан субъектом
    DOCUMENT_HAS_ROLE = "document_has_role"                  # у документа определена роль
    DOCUMENT_HAS_ADDRESS = "document_has_address"            # в документе указан адрес
    DOCUMENT_HAS_BANK_ACCOUNT = "document_has_bank_account"  # в документе указан банковский счёт
    DOCUMENT_HAS_CONTRACT_NUMBER = "document_has_contract_number"  # найден номер договора
