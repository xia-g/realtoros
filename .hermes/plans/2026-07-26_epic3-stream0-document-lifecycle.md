# Epic 3 · Stream 0 — Document Lifecycle Completion

> Implementation plan.

**Goal:** Полностью завершить жизненный цикл документа: добавить `DocumentReady` domain event, `MarkDocumentReady` use case, audit, idempotency, и тесты.

**Architecture:** Product Layer (не Platform). Все изменения — в `backend/services/document_lifecycle.py`, `backend/core/domain_events.py`, `backend/api/routes/documents.py`. Новый эндпоинт `/documents/{id}/mark-ready`.

**Constraints:**
- ADR-030 не менять
- Event Backbone не менять
- Event Store не добавлять
- Aggregate Boundary не менять
- Domain Model вне Lifecycle документа не менять

---

## Task 1: Git — подготовка ветки

**Objective:** Сохранить текущие изменения, переключиться на main, создать новую ветку.

**Files:** нет

**Steps:**
1. `cd /home/xiag/real-estate-os && git stash`
2. `git checkout main && git pull`
3. `git checkout -b feature/epic3-stream0-document-lifecycle`

---

## Task 2: Domain — добавить EVENT_DOCUMENT_READY

**Objective:** Добавить константу `EVENT_DOCUMENT_READY` в `core/domain_events.py`.

**Files:**
- Modify: `backend/core/domain_events.py:90`

**Change:** После `EVENT_DOCUMENT_DELETED = "document.deleted"` добавить:
```python
EVENT_DOCUMENT_READY = "document.ready"
```

---

## Task 3: Domain — DocumentReady event и mark_document_ready() use case

**Objective:** Добавить в `services/document_lifecycle.py`:
- `DocumentReadyEvent` dataclass (или использовать существующий `DomainEvent`)
- `mark_document_ready()` — use case функция
- Инвариант: READY можно установить только один раз
- Валидация: READY только из ANALYZED
- Публикация `DocumentReady` event через существующий DomainEventBus

**Files:**
- Modify: `backend/services/document_lifecycle.py`

**Changes:**

1. В импорты добавить:
```python
from backend.core.domain_events import (
    DomainEvent, DomainEventBus, get_event_bus,
    EVENT_DOCUMENT_READY,
)
from backend.core.audit import get_audit_context, AuditContext
import json
```

2. Добавить в VALID_TRANSITIONS уточнение: READY → [] (терминальный для этого стрима, хотя потом будет ROUTED)

3. Добавить функцию `mark_document_ready()`:
```python
def mark_document_ready(
    doc: Document,
    actor_id: str = "system",
    event_bus: DomainEventBus | None = None,
) -> tuple[str | None, DomainEvent | None]:
    """Mark document as READY. Publishes DocumentReady event.
    
    Returns (error_message, domain_event_or_None).
    Idempotent: if already READY, returns error.
    """
    if doc.status == "READY":
        return "Document is already in READY state", None
    
    if doc.status != "ANALYZED":
        return f"Cannot transition from {doc.status} to READY: only ANALYZED allowed", None
    
    err = transition_document(doc, "READY")
    if err:
        return err, None
    
    # Create and publish DocumentReady event
    event = DomainEvent(
        event_type=EVENT_DOCUMENT_READY,
        entity_type="document",
        entity_id=uuid.UUID(doc.document_id),
        actor_id=actor_id,
        payload={
            "status": "READY",
            "previous_status": "ANALYZED",
            "document_id": doc.document_id,
            "organization_id": doc.organization_id,
            "contract_number": doc.profile.get("fields", {}).get("contract_number", ""),
            "total_price": doc.profile.get("sections", {}).get("financial_terms", {}).get("total_price", {}),
            "buyer_name": doc.profile.get("sections", {}).get("parties", {}).get("buyer", {}).get("name", ""),
            "seller_name": doc.profile.get("sections", {}).get("parties", {}).get("seller", {}).get("name", ""),
            "profile": doc.profile,
        },
    )
    
    bus = event_bus or get_event_bus()
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(bus.emit(event))
    except RuntimeError:
        # No running loop — schedule later or skip
        pass
    
    return None, event
```

---

## Task 4: API — добавить эндпоинт POST /documents/{id}/mark-ready

**Objective:** Добавить выделенный эндпоинт для `MarkDocumentReady` use case.

**Files:**
- Modify: `backend/api/routes/documents.py`

**Changes:**

Добавить эндпоинт в documents.py:

```python
@router.post("/{document_id}/mark-ready")
async def mark_document_ready_endpoint(
    document_id: str,
    request: Request,
):
    """Mark document as READY. Only valid from ANALYZED state.
    
    Publishes DocumentReady domain event.
    Idempotent: returns 400 if already READY.
    """
    from backend.services.document_lifecycle import mark_document_ready as mark_ready_service
    
    repo = _get_repo()
    doc = repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    # Get actor ID from request context
    from backend.core.context import get_request_context
    ctx = get_request_context()
    actor_id = ctx.user_id if ctx and ctx.user_id else "system"
    
    err, event = mark_ready_service(doc, actor_id=actor_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    
    # Update document in DB
    repo.save(doc)
    
    result = _serialize_doc(doc)
    result["event_id"] = str(event.entity_id) if event else None
    result["event_type"] = event.event_type if event else None
    
    return result
```

---

## Task 5: Audit — фиксация перехода в READY

**Objective:** Audit-логирование при переходе в READY.

**Files:**
- Modify: `backend/services/document_lifecycle.py` (внутри `mark_document_ready`)

**Changes:**

Добавить audit-запись в `mark_document_ready()`:

```python
# Audit log
audit_ctx = get_audit_context()
audit_entry = {
    "event": "document.ready",
    "document_id": doc.document_id,
    "actor_id": actor_id,
    "previous_status": "ANALYZED",
    "new_status": "READY",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "correlation_id": audit_ctx.correlation_id if audit_ctx else None,
    "request_id": audit_ctx.request_id if audit_ctx else None,
}
logger = get_logger("lifecycle")
logger.info("document_marked_ready", **audit_entry)
```

Добавить импорт:
```python
from backend.core.logging import get_logger
```

---

## Task 6: Tests — покрытие Stream 0

**Objective:** Добавить тесты для всех сценариев Stream 0.

**Files:**
- Modify: `backend/tests/integration/test_document_lifecycle_api.py`

**Test scenarios:**

1. `test_mark_ready_from_analyzed` — ANALYZED → READY через `/mark-ready`
2. `test_mark_ready_idempotent` — повторный READY → 400
3. `test_mark_ready_from_wrong_state` — READY из UPLOADED → 400
4. `test_mark_ready_event_published` — проверка что DomainEvent создан (проверяем event_id в ответе)
5. `test_mark_ready_not_found` — несуществующий документ → 404
6. `test_lifecycle_regression` — полный жизненный цикл UPLOADED→...→READY всё ещё работает
7. `test_mark_ready_audit_created` — audit-запись создана (проверяем логгер)

---

## Task 7: Verification — запустить тесты

**Objective:** Убедиться, что все тесты проходят.

**Steps:**
1. `cd /home/xiag/real-estate-os && python -m pytest backend/tests/integration/test_document_lifecycle_api.py -v 2>&1`
2. Проверить, что нет регрессий

---

## Definition of Done

- [x] Git: ветка создана от main
- [x] Domain: EVENT_DOCUMENT_READY добавлен
- [x] Domain: read-only проверка READY только из ANALYZED
- [x] Domain: idempotent — повторный READY блокируется
- [x] Domain: DocumentReady event публикуется ровно один раз
- [x] Application: mark_document_ready() use case
- [x] API: POST /documents/{id}/mark-ready endpoint
- [x] Audit: лог перехода
- [x] Tests: 7 сценариев покрыты
- [x] Regression: все существующие тесты проходят
