"""
DocumentRequirementResolver — document_role → deal requirement binding.

DocumentRole (semantic) → deal_document_package (requirement_status = VERIFIED)

Пример:
  document_role = TRANSFER_ACT
  → находит в сделке requirement с document_role = 'transfer_act'
  → устанавливает requirement_status = 'verified'
"""
from __future__ import annotations

from typing import Protocol

from domain.document_semantics.document_role import DocumentRole


# Маппинг: DocumentRole → document_type в document_requirements
ROLE_TO_REQUIREMENT_KEY: dict[DocumentRole, str] = {
    DocumentRole.SALE_CONTRACT: "dkp",
    DocumentRole.TRANSFER_ACT: "acceptance_act",
    DocumentRole.EGRN_EXTRACT: "egrn_extract",
    DocumentRole.PAYMENT_ORDER: "payment_order",
    DocumentRole.PASSPORT: "passport_seller",
    DocumentRole.INVOICE: "invoice",
    DocumentRole.RECEIPT: "receipt",
    DocumentRole.CERTIFICATE: "certificate",
    DocumentRole.CADASTRAL: "cadastral_passport",
    DocumentRole.RECONCILIATION: "reconciliation_act",
    DocumentRole.ADVANCE_REPORT: "advance_report",
}


class DealStore(Protocol):
    """Протокол для обновления требований сделки."""

    async def get_requirement_package(
        self, deal_id: str, requirement_key: str
    ) -> dict | None: ...

    async def set_requirement_status(
        self, package_id: str, status: str, document_id: str | None = None
    ) -> None: ...

    async def get_deal_by_document(self, document_id: str) -> dict | None: ...


class DocumentRequirementResolver:
    """Связывает document_role с requirement сделки."""

    def __init__(self, store: DealStore):
        self._store = store

    async def resolve(
        self,
        deal_id: str,
        document_role: DocumentRole,
        document_id: str,
    ) -> dict:
        """Привязать документ к требованию сделки.

        Находит requirement по document_role и отмечает как VERIFIED.
        """
        req_key = ROLE_TO_REQUIREMENT_KEY.get(document_role)
        if not req_key:
            return {"matched": False, "reason": f"Нет маппинга для роли {document_role.value}"}

        pkg = await self._store.get_requirement_package(deal_id, req_key)
        if not pkg:
            return {"matched": False, "reason": f"Нет требования {req_key} в сделке {deal_id}"}

        await self._store.set_requirement_status(
            pkg["package_id"], "verified", document_id
        )

        return {
            "matched": True,
            "package_id": pkg["package_id"],
            "requirement_key": req_key,
            "label": pkg.get("label", ""),
            "new_status": "verified",
        }
