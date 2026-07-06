"""Compliance Engine — проверка сделки на полноту.

Оценивает сделку по чекпоинтам, документам и регуляторным требованиям.
Возвращает compliance score и список недостающих элементов.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class ComplianceItem:
    """Один элемент проверки compliance."""
    item_type: str  # checkpoint | document | regulation
    key: str
    label: str
    status: str  # completed | missing | pending
    severity: str = "required"  # required | recommended | optional
    details: str | None = None


@dataclass
class ComplianceResult:
    """Результат проверки compliance."""
    deal_id: UUID
    compliance_score: float  # 0.0 - 100.0
    total_items: int
    completed_items: int
    missing_items: int
    items: list[ComplianceItem] = field(default_factory=list)
    stage_summary: dict[str, dict] = field(default_factory=dict)
    status: str = "compliant"


class ComplianceService:
    """Проверяет сделку на соответствие требованиям."""

    # Статическая карта этапов и чекпоинтов для каждого типа сделки
    DEAL_STAGES = {
        "SALE_APARTMENT": [
            ("NEW", [
                ("client_verified", "Клиент верифицирован"),
                ("object_verified", "Объект проверен"),
                ("ownership_verified", "Право собственности подтверждено"),
            ]),
            ("PREPARATION", [
                ("agreement_draft", "Проект договора"),
                ("bank_documents", "Банковские документы"),
                ("seller_documents", "Документы продавца"),
            ]),
            ("SIGNING", [
                ("contract_signed", "Договор подписан"),
                ("transfer_act_signed", "Акт приёма-передачи подписан"),
            ]),
            ("REGISTRATION", [
                ("rosreestr_submitted", "Документы поданы в Росреестр"),
                ("registration_completed", "Регистрация завершена"),
            ]),
        ],
        "MORTGAGE": [
            ("NEW", [
                ("client_verified", "Клиент верифицирован"),
                ("object_verified", "Объект проверен"),
                ("ownership_verified", "Право собственности подтверждено"),
            ]),
            ("PREPARATION", [
                ("mortgage_approval", "Одобрение ипотеки"),
                ("insurance", "Страхование"),
                ("income_confirmation", "Подтверждение дохода"),
                ("bank_documents", "Банковские документы"),
            ]),
            ("SIGNING", [
                ("contract_signed", "Кредитный договор подписан"),
                ("insurance_policy", "Полис страхования оформлен"),
            ]),
            ("REGISTRATION", [
                ("rosreestr_submitted", "Документы поданы в Росреестр"),
                ("registration_completed", "Регистрация завершена"),
            ]),
        ],
        "RENT": [
            ("NEW", [
                ("client_verified", "Клиент верифицирован"),
                ("object_verified", "Объект проверен"),
            ]),
            ("PREPARATION", [
                ("agreement_draft", "Проект договора аренды"),
                ("deposit_received", "Депозит получен"),
            ]),
            ("SIGNING", [
                ("contract_signed", "Договор аренды подписан"),
                ("transfer_act_signed", "Акт приёма-передачи подписан"),
            ]),
        ],
    }

    # Документы по типам сделок
    DEAL_DOCUMENTS = {
        "SALE_APARTMENT": [
            ("passport_seller", "Паспорт продавца", True),
            ("passport_buyer", "Паспорт покупателя", True),
            ("ownership_extract", "Выписка ЕГРН", True),
            ("purchase_agreement", "Договор купли-продажи", True),
            ("spouse_consent", "Согласие супруга", False),
            ("encumbrance_check", "Проверка обременений", True),
        ],
        "MORTGAGE": [
            ("mortgage_approval", "Одобрение ипотеки", True),
            ("insurance", "Полис страхования", True),
            ("income_confirmation", "Подтверждение дохода", True),
            ("passport_buyer", "Паспорт заёмщика", True),
            ("ownership_extract", "Выписка ЕГРН", True),
        ],
        "RENT": [
            ("passport_tenant", "Паспорт арендатора", True),
            ("passport_landlord", "Паспорт арендодателя", True),
            ("rental_agreement", "Договор аренды", True),
            ("deposit_receipt", "Расписка о депозите", False),
        ],
    }

    def __init__(
        self,
        checkpoint_repo=None,
        document_repo=None,
        regulation_repo=None,
    ):
        self._checkpoint_repo = checkpoint_repo
        self._document_repo = document_repo
        self._regulation_repo = regulation_repo

    async def evaluate_deal(
        self,
        deal_id: UUID,
        deal_type: str,
        completed_checkpoints: list[str] | None = None,
        uploaded_documents: list[str] | None = None,
    ) -> ComplianceResult:
        """Оценить сделку: чекпоинты + документы + регуляции."""
        items: list[ComplianceItem] = []
        stage_summary: dict[str, dict] = {}
        completed = 0
        total = 0

        completed_checkpoints = completed_checkpoints or []
        uploaded_documents = uploaded_documents or []

        # 1. Проверка чекпоинтов
        stages = self.DEAL_STAGES.get(deal_type, self.DEAL_STAGES["SALE_APARTMENT"])
        for stage_name, checkpoints in stages:
            stage_total = len(checkpoints)
            stage_done = sum(1 for ck, _ in checkpoints if ck in completed_checkpoints)
            stage_summary[stage_name] = {
                "total": stage_total,
                "completed": stage_done,
                "percent": round(stage_done / stage_total * 100, 1) if stage_total else 100,
            }

            for ck, label in checkpoints:
                total += 1
                if ck in completed_checkpoints:
                    completed += 1
                    items.append(ComplianceItem(
                        item_type="checkpoint", key=ck, label=label,
                        status="completed", severity="required",
                    ))
                else:
                    items.append(ComplianceItem(
                        item_type="checkpoint", key=ck, label=label,
                        status="missing", severity="required",
                    ))

        # 2. Проверка документов
        docs = self.DEAL_DOCUMENTS.get(deal_type, self.DEAL_DOCUMENTS["SALE_APARTMENT"])
        for doc_type, label, is_required in docs:
            total += 1
            if doc_type in uploaded_documents:
                completed += 1
                items.append(ComplianceItem(
                    item_type="document", key=doc_type, label=label,
                    status="completed", severity="required" if is_required else "recommended",
                ))
            else:
                items.append(ComplianceItem(
                    item_type="document", key=doc_type, label=label,
                    status="missing", severity="required" if is_required else "recommended",
                ))

        score = round(completed / total * 100, 1) if total else 100.0
        missing = total - completed
        status = "compliant" if score >= 100 else "partial" if score >= 50 else "non_compliant"

        return ComplianceResult(
            deal_id=deal_id,
            compliance_score=score,
            total_items=total,
            completed_items=completed,
            missing_items=missing,
            items=items,
            stage_summary=stage_summary,
            status=status,
        )

    async def check_deal_completeness(self, deal_id: UUID, deal_type: str, **kwargs) -> dict:
        """MCP-ready: возвращает словарь с результатом проверки."""
        result = await self.evaluate_deal(deal_id, deal_type, **kwargs)

        missing_items = [
            {"key": i.key, "label": i.label, "type": i.item_type, "severity": i.severity}
            for i in result.items if i.status == "missing"
        ]

        return {
            "deal_id": str(deal_id),
            "compliance_score": result.compliance_score,
            "status": result.status,
            "total_items": result.total_items,
            "completed_items": result.completed_items,
            "missing_items_count": result.missing_items,
            "missing_items": missing_items,
            "stage_summary": result.stage_summary,
        }

    async def validate_document_package(self, deal_type: str, uploaded: list[str]) -> dict:
        """MCP-ready: проверяет комплект документов."""
        docs = self.DEAL_DOCUMENTS.get(deal_type, self.DEAL_DOCUMENTS["SALE_APARTMENT"])

        present = []
        missing_required = []
        missing_recommended = []

        for doc_type, label, is_required in docs:
            entry = {"type": doc_type, "label": label, "is_required": is_required}
            if doc_type in uploaded:
                entry["status"] = "present"
                present.append(entry)
            elif is_required:
                entry["status"] = "missing_required"
                missing_required.append(entry)
            else:
                entry["status"] = "missing_recommended"
                missing_recommended.append(entry)

        completeness = round(
            (len(present) / len(docs)) * 100, 1
        ) if docs else 100.0

        return {
            "deal_type": deal_type,
            "document_completeness": completeness,
            "total_required": len(docs),
            "present": len(present),
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
        }

    async def check_registration_readiness(self, deal_id: UUID, deal_type: str, **kwargs) -> dict:
        """Проверить готовность сделки к регистрации в Росреестре."""
        result = await self.evaluate_deal(deal_id, deal_type, **kwargs)
        required_for_registration = [
            "contract_signed", "transfer_act_signed",
            "passport_seller", "passport_buyer", "ownership_extract",
        ]
        has_contract = any(
            i.status == "completed" and i.key in ("contract_signed", "purchase_agreement")
            for i in result.items
        )
        has_passports = all(
            any(i.status == "completed" and i.key == k for i in result.items)
            for k in ["passport_seller", "passport_buyer"]
        )
        has_extract = any(
            i.status == "completed" and i.key == "ownership_extract" for i in result.items
        )
        ready = has_contract and has_passports and has_extract
        missing = []
        if not has_contract: missing.append("Подписанный договор")
        if not has_passports: missing.append("Паспорта сторон")
        if not has_extract: missing.append("Выписка ЕГРН")
        return {
            "deal_id": str(deal_id),
            "registration_ready": ready,
            "compliance_score": result.compliance_score,
            "missing_for_registration": missing,
        }

    async def check_stage_compliance(self, deal_id: UUID, deal_type: str, stage: str, **kwargs) -> dict:
        """Проверить compliance для конкретного этапа сделки."""
        result = await self.evaluate_deal(deal_id, deal_type, **kwargs)
        stage_items = [i for i in result.items if getattr(i, "stage", "") == stage]
        stage_score = 0.0
        stage_total = len(stage_items)
        if stage_total:
            stage_completed = sum(1 for i in stage_items if i.status == "completed")
            stage_score = round(stage_completed / stage_total * 100, 1)
        return {
            "deal_id": str(deal_id),
            "stage": stage,
            "stage_score": stage_score,
            "stage_items": [{"key": i.key, "status": i.status, "severity": i.severity} for i in stage_items],
        }

    async def generate_compliance_report(self, deal_id: UUID, deal_type: str, **kwargs) -> dict:
        """Сгенерировать полный compliance-отчёт по сделке."""
        result = await self.evaluate_deal(deal_id, deal_type, **kwargs)
        readiness = await self.check_registration_readiness(deal_id, deal_type, **kwargs)
        blocking_issues = [
            {"key": i.key, "label": i.label} for i in result.items
            if i.status == "missing" and i.severity == "required"
        ]
        return {
            "deal_id": str(deal_id),
            "compliance_score": result.compliance_score,
            "status": result.status,
            "stage_summary": result.stage_summary,
            "total_items": result.total_items,
            "completed_items": result.completed_items,
            "missing_items": result.missing_items,
            "blocking_issues": blocking_issues,
            "registration_readiness": readiness.get("registration_ready", False),
            "missing_for_registration": readiness.get("missing_for_registration", []),
        }
