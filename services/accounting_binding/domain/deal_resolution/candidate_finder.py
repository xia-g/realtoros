"""
CandidateFinder — поиск кандидатов по 5 независимым индексам.

Источники:
  - cadastral_number
  - normalized_address
  - parties (buyer/seller INN)
  - contract_number
  - date proximity

Не вычисляет similarity — только поиск + дедупликация.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from domain.deal_resolution.fingerprint import TransactionFingerprint


class CandidateTransaction:
    """Кандидат — существующая сделка/транзакция."""

    def __init__(
        self,
        deal_id: str,
        deal_type: str,
        title: str,
        status: str,
        lifecycle_stage: str,
        contract_number: str = "",
        contract_date: date | None = None,
        amount: float = 0.0,
        buyer: str = "",
        seller: str = "",
        cadastral_number: str = "",
        address: str = "",
        created_at: str = "",
    ):
        self.deal_id = deal_id
        self.deal_type = deal_type
        self.title = title
        self.status = status
        self.lifecycle_stage = lifecycle_stage
        self.contract_number = contract_number
        self.contract_date = contract_date
        self.amount = amount
        self.buyer = buyer
        self.seller = seller
        self.cadastral_number = cadastral_number
        self.address = address
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "deal_id": self.deal_id,
            "deal_type": self.deal_type,
            "title": self.title,
            "status": self.status,
            "lifecycle_stage": self.lifecycle_stage,
            "contract_number": self.contract_number,
            "contract_date": str(self.contract_date) if self.contract_date else "",
            "amount": self.amount,
            "buyer": self.buyer,
            "seller": self.seller,
            "cadastral_number": self.cadastral_number,
            "address": self.address,
        }


class DealStore(Protocol):
    """Протокол хранилища сделок для поиска."""

    async def find_by_cadastral(self, cadastral: str) -> list[dict]: ...
    async def find_by_address(self, address: str) -> list[dict]: ...
    async def find_by_parties(self, buyer: str, seller: str, inn: str) -> list[dict]: ...
    async def find_by_contract(self, contract_number: str) -> list[dict]: ...
    async def find_by_date_range(self, doc_date: date | None, days: int = 30) -> list[dict]: ...


class CandidateFinder:
    """Поиск кандидатов по нескольким индексам."""

    def __init__(self, store: DealStore):
        self._store = store

    async def find_candidates(self, fp: TransactionFingerprint) -> list[CandidateTransaction]:
        """Найти кандидатов по всем индексам. Merge + dedup."""
        seen: set[str] = set()
        candidates: list[CandidateTransaction] = []

        # 1. By cadastral number
        if fp.property_identity and fp.property_identity.cadastral_number:
            for row in await self._store.find_by_cadastral(fp.property_identity.cadastral_number):
                if row["id"] not in seen:
                    seen.add(row["id"])
                    candidates.append(self._row_to_candidate(row))

        # 2. By address
        if fp.property_identity and fp.property_identity.normalized_address:
            for row in await self._store.find_by_address(fp.property_identity.normalized_address):
                if row["id"] not in seen:
                    seen.add(row["id"])
                    candidates.append(self._row_to_candidate(row))

        # 3. By parties
        inn = fp.buyer_inn or fp.seller_inn
        if fp.buyer or fp.seller:
            for row in await self._store.find_by_parties(fp.buyer, fp.seller, inn):
                if row["id"] not in seen:
                    seen.add(row["id"])
                    candidates.append(self._row_to_candidate(row))

        # 4. By contract number
        if fp.contract_number:
            for row in await self._store.find_by_contract(fp.contract_number):
                if row["id"] not in seen:
                    seen.add(row["id"])
                    candidates.append(self._row_to_candidate(row))

        # 5. By date proximity
        if fp.contract_date:
            for row in await self._store.find_by_date_range(fp.contract_date, days=30):
                if row["id"] not in seen:
                    seen.add(row["id"])
                    candidates.append(self._row_to_candidate(row))

        return candidates

    def _row_to_candidate(self, row: dict) -> CandidateTransaction:
        return CandidateTransaction(
            deal_id=str(row.get("id", "")),
            deal_type=row.get("deal_type", ""),
            title=row.get("title", ""),
            status=row.get("status", ""),
            lifecycle_stage=row.get("lifecycle_stage", ""),
            contract_number=row.get("contract_number", ""),
            contract_date=row.get("contract_date"),
            amount=float(row.get("price", 0) or 0),
            buyer=row.get("buyer", ""),
            seller=row.get("seller", ""),
            cadastral_number=row.get("cadastral_number", ""),
            address=row.get("address", ""),
        )
