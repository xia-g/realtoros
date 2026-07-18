"""Document Package Manager — система контроля комплектности."""

from __future__ import annotations

from uuid import UUID, uuid4

from structlog import get_logger

from backend.core.domain_events import (
    DomainEvent, get_event_bus,
    EVENT_DOCUMENT_CREATED, EVENT_DOCUMENT_DELETED,
)

logger = get_logger(__name__)


class DocumentPackageService:
    """Управляет комплектом документов сделки.

    Поддерживает: required, optional, conditional.
    """

    def __init__(self, session):
        self.session = session

    async def attach_document(self, package_id: UUID, document_id: UUID, user_id: UUID) -> dict:
        from backend.models.deal_document_package import DealDocumentPackage
        from sqlalchemy import select
        result = await self.session.execute(
            select(DealDocumentPackage).where(DealDocumentPackage.id == package_id)
        )
        pkg = result.scalar_one_or_none()
        if not pkg:
            return {"success": False, "error": "Package not found"}
        pkg.document_id = document_id
        pkg.status = "attached"
        pkg.attached_by = user_id
        await self.session.flush()
        logger.info("document_attached", package_id=str(package_id), document_id=str(document_id))
        bus = get_event_bus()
        await bus.emit(DomainEvent(
            event_type=EVENT_DOCUMENT_CREATED,
            entity_type="document",
            entity_id=document_id,
            correlation_id=str(uuid4()),
            actor_id=str(user_id) if user_id else "system",
            payload={"package_id": str(package_id)},
        ))
        return {"success": True, "status": "attached"}

    async def detach_document(self, package_id: UUID) -> dict:
        from backend.models.deal_document_package import DealDocumentPackage
        from sqlalchemy import select
        result = await self.session.execute(
            select(DealDocumentPackage).where(DealDocumentPackage.id == package_id)
        )
        pkg = result.scalar_one_or_none()
        if not pkg:
            return {"success": False, "error": "Package not found"}
        pkg.document_id = None
        pkg.status = "missing"
        pkg.attached_by = None
        await self.session.flush()
        logger.info("document_detached", package_id=str(package_id))
        bus = get_event_bus()
        await bus.emit(DomainEvent(
            event_type=EVENT_DOCUMENT_DELETED,
            entity_type="document",
            entity_id=UUID(int=0),  # placeholder
            correlation_id=str(uuid4()),
            payload={"package_id": str(package_id)},
        ))
        return {"success": True, "status": "detached"}

    async def calculate_completeness(self, deal_id: UUID) -> dict:
        from backend.models.deal_document_package import DealDocumentPackage
        from sqlalchemy import func, select, case, Integer
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.sum(case((DealDocumentPackage.status == "attached", 1), else_=0)).label("attached"),
            ).where(DealDocumentPackage.deal_id == deal_id, DealDocumentPackage.deleted_at.is_(None))
        )
        row = result.one()
        total = row.total or 0
        attached = row.attached or 0
        return {
            "total": total,
            "attached": attached,
            "missing": total - attached,
            "completeness": round(attached / total * 100, 1) if total else 100.0,
        }

    async def list_missing(self, deal_id: UUID) -> list[dict]:
        from backend.models.deal_document_package import DealDocumentPackage
        from sqlalchemy import select
        result = await self.session.execute(
            select(DealDocumentPackage)
            .where(DealDocumentPackage.deal_id == deal_id, DealDocumentPackage.status == "missing", DealDocumentPackage.deleted_at.is_(None))
        )
        pkgs = result.scalars().all()
        return [{"id": str(p.id), "requirement_id": str(p.requirement_id), "status": p.status} for p in pkgs]
