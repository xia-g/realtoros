"""
Agreement types and participant roles — business semantics for v2.0.2.

Determined by SemanticInterpreter from neutral facts.
NOT used by Extraction layer (v2.0.1a).
"""
from __future__ import annotations

from enum import Enum


class AgreementType(str, Enum):
    SALE = "sale"                # договор купли-продажи
    PURCHASE = "purchase"        # договор покупки
    LEASE = "lease"              # договор аренды
    SERVICE = "service"          # договор оказания услуг
    AGENCY = "agency"            # агентский договор
    COMMISSION = "commission"    # договор комиссии
    FRAMEWORK = "framework"      # рамочный договор
    LOAN = "loan"                # договор займа
    OFFER = "offer"              # счёт-оферта
    UNKNOWN = "unknown"          # не удалось определить


class ParticipantRole(str, Enum):
    SELLER = "seller"            # продавец
    BUYER = "buyer"              # покупатель
    LANDLORD = "landlord"        # арендодатель
    TENANT = "tenant"            # арендатор
    CUSTOMER = "customer"        # заказчик
    SUPPLIER = "supplier"        # поставщик
    PRINCIPAL = "principal"      # принципал
    AGENT = "agent"              # агент
    CONTRACTOR = "contractor"    # исполнитель
    CLIENT = "client"            # клиент
    REPRESENTATIVE = "representative"  # представитель
    UNKNOWN = "unknown"
