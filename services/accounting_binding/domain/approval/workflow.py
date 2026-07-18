"""
Domain — Approval.

Workflow управления жизненным циклом accounting_document.
Только approval-переходы. Posting — отдельный домен.

Revision guard: approved_mapping_hash == current_mapping_hash.
Stale approval → не допускает POST.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from contracts import AccountingDocument, DocumentStatus


class ApprovalAction(Enum):
    """Действия approval workflow."""
    SUBMIT = auto()          # DRAFT → READY
    REQUEST_REVIEW = auto()  # READY → REVIEW
    APPROVE = auto()         # REVIEW → APPROVED
    REJECT = auto()          # REVIEW → REJECTED
    RESET_TO_DRAFT = auto()  # REVIEW/REJECTED → DRAFT


# Разрешённые переходы — только approval, НЕ posting
TRANSITIONS: dict[DocumentStatus, dict[ApprovalAction, DocumentStatus]] = {
    DocumentStatus.DRAFT: {
        ApprovalAction.SUBMIT: DocumentStatus.READY,
    },
    DocumentStatus.READY: {
        ApprovalAction.REQUEST_REVIEW: DocumentStatus.REVIEW,
    },
    DocumentStatus.REVIEW: {
        ApprovalAction.APPROVE: DocumentStatus.APPROVED,
        ApprovalAction.REJECT: DocumentStatus.REJECTED,
        ApprovalAction.RESET_TO_DRAFT: DocumentStatus.DRAFT,
    },
    DocumentStatus.APPROVED: {
        # POST — только через PostingService.post(), не здесь
    },
    DocumentStatus.REJECTED: {
        ApprovalAction.RESET_TO_DRAFT: DocumentStatus.DRAFT,
    },
    DocumentStatus.POSTED: {},
}


class InvalidTransitionError(ValueError):
    """Недопустимый переход статуса."""
    pass


class StaleApprovalError(ValueError):
    """Документ изменился после approval: mapping_hash не совпадает."""
    pass


@dataclass
class ApprovalEvent:
    """Событие изменения статуса (audit trail)."""
    document_id: str
    from_status: DocumentStatus
    to_status: DocumentStatus
    action: ApprovalAction
    by_user: str = ""
    comment: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ApprovalWorkflow:
    """Workflow управления статусами — только approval.

    При APPROVE фиксирует mapping_hash → revision.
    Posting проверяет approved_mapping_hash == current_mapping_hash.
    """

    def apply(
        self,
        doc: AccountingDocument,
        action: ApprovalAction,
        by_user: str = "",
        comment: str = "",
    ) -> tuple[AccountingDocument, ApprovalEvent]:
        """Применить approval-действие.

        При APPROVE: сохраняет approved_mapping_hash, инкрементит revision.
        При RESET_TO_DRAFT: сбрасывает revision.
        """
        current = doc.status
        allowed = TRANSITIONS.get(current, {})

        if action not in allowed:
            raise InvalidTransitionError(
                f"Недопустимый переход: {current.value} → {action.name} "
                f"(разрешены: {[a.name for a in allowed]})"
            )

        new_status = allowed[action]
        event = ApprovalEvent(
            document_id=doc.document_id,
            from_status=current,
            to_status=new_status,
            action=action,
            by_user=by_user,
            comment=comment,
        )

        # При APPROVE фиксируем mapping_hash как approved
        data = dict(doc)
        if new_status == DocumentStatus.APPROVED:
            data["approved_mapping_hash"] = doc.mapping_hash
            data["approval_revision"] = doc.approval_revision + 1
        elif new_status == DocumentStatus.DRAFT and action == ApprovalAction.RESET_TO_DRAFT:
            data["approved_mapping_hash"] = ""
            data["approval_revision"] = 0

        data["status"] = new_status
        updated = doc.__class__(**data)
        return updated, event

    def check_approval_valid(
        self, doc: AccountingDocument
    ) -> None:
        """Проверить, что approval не stale.

        Документ мог измениться после APPROVE:
        approved_mapping_hash != current mapping_hash → STALE_APPROVAL.
        """
        if doc.status == DocumentStatus.APPROVED:
            if doc.approved_mapping_hash and doc.approved_mapping_hash != doc.mapping_hash:
                raise StaleApprovalError(
                    f"Approval stale: approved mapping changed "
                    f"(revision {doc.approval_revision})"
                )
