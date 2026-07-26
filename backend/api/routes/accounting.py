"""Epic 2 / Stream 1 — Accounting API.

Endpoints:
  POST   /accounting/entries                          — Create entry
  GET    /accounting/entries/{id}                     — Get entry
  GET    /accounting/entries                          — List entries
  POST   /accounting/entries/{id}/validate            — Validate
  POST   /accounting/entries/{id}/post                — Post (immutable)
  POST   /accounting/documents/{id}/create-entry      — Auto from document
  GET    /accounting/ledger/{account_id}              — Account turnover
  GET    /accounting/trial-balance                    — Trial balance
  GET    /accounting/accounts                         — Chart of accounts
  GET    /accounting/journal                          — Journal
  GET    /accounting/ledger/{id}/entries              — Ledger detail
  GET    /accounting/periods                          — Period list
  GET    /accounting/balance-sheet                    — Balance sheet
  GET    /accounting/profit-loss                      — P&L
  POST   /accounting/reconciliation/start             — Start reconciliation
  GET    /accounting/reconciliation/{run_id}          — Get reconciliation
  POST   /accounting/reconciliation/{run_id}/match    — Match line
  POST   /accounting/reconciliation/{run_id}/resolve  — Resolve
  POST   /accounting/periods/{id}/close               — Multi-step close
  GET    /accounting/periods/{id}/close-log           — Close log

Product Layer, not Platform.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from backend.services.accounting.repository import AccountingRepository
from backend.services.accounting.models import (
    AccountingEntry, EntryLine, EntryStatus,
)
from backend.services.accounting.mapper import AccountingMapper
from backend.services.accounting.posting import PostingService
from backend.services.accounting.reporting import ReportingService
from backend.services.accounting.reconciliation import ReconciliationService
from backend.services.accounting.closing import PeriodCloser

router = APIRouter(prefix="/accounting", tags=["Accounting Engine"])


def _repo(request: Request) -> AccountingRepository:
    from backend.config import settings
    return AccountingRepository(settings.DATABASE_SYNC_URL)


def _serialize_entry(entry: AccountingEntry) -> dict:
    return {
        "entry_id": entry.entry_id,
        "journal_id": entry.journal_id,
        "document_id": entry.document_id,
        "period_id": entry.period_id,
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "description": entry.description,
        "status": entry.status,
        "total_debit": str(entry.total_debit),
        "total_credit": str(entry.total_credit),
        "is_balanced": entry.is_balanced,
        "lines": [
            {
                "line_id": l.line_id,
                "account_id": l.account_id,
                "debit": str(l.debit),
                "credit": str(l.credit),
                "counterparty_id": l.counterparty_id,
                "description": l.description,
            }
            for l in entry.lines
        ],
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "posted_at": entry.posted_at.isoformat() if entry.posted_at else None,
    }


# ─── Accounts ──────────────────────────────────────────────────


@router.get("/accounts")
async def list_accounts(request: Request):
    r = _repo(request)
    accounts = r.list_accounts()
    return {
        "accounts": [
            {
                "account_id": a.account_id, "code": a.code, "name": a.name,
                "type": a.account_type.value, "parent_id": a.parent_id,
                "is_active": a.is_active,
            }
            for a in accounts
        ]
    }


# ─── Entries ───────────────────────────────────────────────────


@router.post("/entries")
async def create_entry(body: dict, request: Request):
    from decimal import Decimal
    r = _repo(request)
    entry_id = str(uuid.uuid4())
    lines_data = body.get("lines", [])
    entry_date_str = body.get("entry_date", "")
    try:
        parts = entry_date_str.split("-")
        entry_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        entry_date = date.today()

    entry = AccountingEntry(
        entry_id=entry_id,
        journal_id=body.get("journal_id", "journal-general"),
        document_id=body.get("document_id", ""),
        period_id=body.get("period_id", "period-current"),
        entry_date=entry_date,
        description=body.get("description", ""),
        status="DRAFT",
        created_at=datetime.now(timezone.utc),
    )
    for ld in lines_data:
        entry.lines.append(EntryLine(
            line_id=str(uuid.uuid4()), entry_id=entry_id,
            account_id=str(ld.get("account_id", "")),
            debit=Decimal(str(ld.get("debit", "0"))),
            credit=Decimal(str(ld.get("credit", "0"))),
            counterparty_id=ld.get("counterparty_id"),
            description=str(ld.get("description", "")),
        ))
    r.save_entry(entry)
    return _serialize_entry(r.get_entry(entry.entry_id))


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: str, request: Request):
    r = _repo(request)
    entry = r.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Entry not found: {entry_id}")
    return _serialize_entry(entry)


@router.get("/entries")
async def list_entries(
    period_id: str = Query(None), document_id: str = Query(None),
    status: str = Query(None), limit: int = Query(50),
    request: Request = None,
):
    r = _repo(request)
    entries = r.list_entries(period_id=period_id, document_id=document_id,
                             status=status, limit=limit)
    return {"entries": [_serialize_entry(e) for e in entries]}


@router.post("/entries/{entry_id}/validate")
async def validate_entry(entry_id: str, request: Request):
    r = _repo(request)
    err = r.update_entry_status(entry_id, "VALIDATED")
    if err:
        raise HTTPException(status_code=400, detail=err)
    return _serialize_entry(r.get_entry(entry_id))


@router.post("/entries/{entry_id}/post")
async def post_entry(entry_id: str, request: Request):
    from backend.config import settings
    svc = PostingService(settings.DATABASE_SYNC_URL)
    err = svc.post_entry(entry_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return _serialize_entry(_repo(request).get_entry(entry_id))


# ─── Journal ───────────────────────────────────────────────────


@router.get("/journal")
async def list_journal(period_id: str = Query("period-current"),
                        limit: int = Query(100), request: Request = None):
    from backend.config import settings
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT je.*, ae.description, ae.status
                FROM journal_entries je
                JOIN accounting_entries ae ON je.entry_id = ae.entry_id
                WHERE je.period_id = %s
                ORDER BY je.sequence_number LIMIT %s
            """, (period_id, limit))
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "period_id": period_id,
        "journal_entries": [
            {
                "journal_entry_id": r["journal_entry_id"],
                "entry_id": r["entry_id"],
                "posting_date": r["posting_date"].isoformat() if r.get("posting_date") else None,
                "sequence_number": r["sequence_number"],
                "description": r.get("description", ""),
                "status": r.get("status", ""),
            }
            for r in rows
        ],
    }


# ─── Ledger ────────────────────────────────────────────────────


@router.get("/ledger/{account_id}")
async def get_account_turnover(
    account_id: str, period_id: str = Query("period-current"),
    start_date: str = Query(None), end_date: str = Query(None),
    request: Request = None,
):
    r = _repo(request)
    sd = date.fromisoformat(start_date) if start_date else None
    ed = date.fromisoformat(end_date) if end_date else None
    return r.get_account_turnover(account_id, period_id, sd, ed)


@router.get("/ledger/{account_id}/entries")
async def get_ledger_entries(
    account_id: str, period_id: str = Query("period-current"),
    request: Request = None,
):
    from backend.config import settings
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT le.*, ae.description as entry_description
                FROM ledger_entries le
                JOIN accounting_entries ae ON le.entry_id = ae.entry_id
                WHERE le.account_id = %s AND le.period_id = %s
                ORDER BY le.posting_date, le.ledger_entry_id
            """, (account_id, period_id))
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "account_id": account_id, "period_id": period_id,
        "entries": [
            {
                "ledger_entry_id": r["ledger_entry_id"],
                "entry_id": r["entry_id"],
                "posting_date": r["posting_date"].isoformat() if r.get("posting_date") else None,
                "debit": str(r["debit"]), "credit": str(r["credit"]),
                "balance_after": str(r["balance_after"]),
                "description": r.get("entry_description", ""),
            }
            for r in rows
        ],
    }


# ─── Reporting ─────────────────────────────────────────────────


@router.get("/trial-balance")
async def get_trial_balance(period_id: str = Query("period-current"),
                             request: Request = None):
    from backend.config import settings
    return ReportingService(settings.DATABASE_SYNC_URL).get_trial_balance(period_id)


@router.get("/balance-sheet")
async def get_balance_sheet(period_id: str = Query("period-current"),
                             request: Request = None):
    from backend.config import settings
    return ReportingService(settings.DATABASE_SYNC_URL).get_balance_sheet(period_id)


@router.get("/profit-loss")
async def get_profit_loss(period_id: str = Query("period-current"),
                           request: Request = None):
    from backend.config import settings
    return ReportingService(settings.DATABASE_SYNC_URL).get_profit_loss(period_id)


# ─── Periods ───────────────────────────────────────────────────


@router.get("/periods")
async def list_periods(request: Request = None):
    from backend.config import settings
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM accounting_periods ORDER BY start_date DESC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "periods": [
            {
                "period_id": r["period_id"], "name": r["name"],
                "start_date": r["start_date"].isoformat() if r.get("start_date") else None,
                "end_date": r["end_date"].isoformat() if r.get("end_date") else None,
                "status": r["status"],
            }
            for r in rows
        ],
    }


@router.post("/periods/{period_id}/close")
async def close_period(period_id: str, request: Request = None):
    from backend.config import settings
    closer = PeriodCloser(settings.DATABASE_SYNC_URL)
    log = closer.close_period(period_id)
    success = all(s["status"] == "OK" for s in log)
    return {"period_id": period_id, "success": success, "steps": log}


@router.get("/periods/{period_id}/close-log")
async def get_period_close_log(period_id: str, request: Request = None):
    from backend.config import settings
    closer = PeriodCloser(settings.DATABASE_SYNC_URL)
    return {"period_id": period_id, "steps": closer.get_close_log(period_id)}


# ─── Reconciliation ────────────────────────────────────────────


@router.post("/reconciliation/start")
async def start_reconciliation(
    period_id: str = Query(...), account_id: str = Query("51"),
    statement_balance: float = Query(0.0), request: Request = None,
):
    from backend.config import settings
    svc = ReconciliationService(settings.DATABASE_SYNC_URL)
    return svc.start_reconciliation(period_id, account_id, statement_balance)


@router.get("/reconciliation/{run_id}")
async def get_reconciliation(run_id: str, request: Request = None):
    from backend.config import settings
    svc = ReconciliationService(settings.DATABASE_SYNC_URL)
    run = svc.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return run


@router.post("/reconciliation/{run_id}/match")
async def match_reconciliation_line(run_id: str, body: dict, request: Request = None):
    from backend.config import settings
    svc = ReconciliationService(settings.DATABASE_SYNC_URL)
    line_id = body.get("line_id", "")
    match_ref = body.get("match_ref", "manual")
    err = svc.match_line(run_id, line_id, match_ref)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return svc.get_run(run_id)


@router.post("/reconciliation/{run_id}/resolve")
async def resolve_reconciliation(run_id: str, request: Request = None):
    from backend.config import settings
    svc = ReconciliationService(settings.DATABASE_SYNC_URL)
    err = svc.resolve_reconciliation(run_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return svc.get_run(run_id)


# ─── Document → Entry ──────────────────────────────────────────


@router.post("/documents/{document_id}/create-entry")
async def create_entry_from_document(document_id: str, request: Request):
    from backend.services.document_lifecycle import DocumentRepository
    from backend.config import settings
    doc_repo = DocumentRepository(dsn=settings.DATABASE_SYNC_URL)
    doc = doc_repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    profile = doc.profile or {}
    doc_type = profile.get("document_type", "")
    fields = profile.get("fields", {})
    mapper = AccountingMapper()
    entry = mapper.map_to_entry(document_id=document_id, doc_type=doc_type,
                                fields=fields, period_id="period-current")
    if entry is None:
        raise HTTPException(status_code=400,
                            detail=f"No accounting mapping for document type '{doc_type}'")
    r = _repo(request)
    r.save_entry(entry)
    return _serialize_entry(r.get_entry(entry.entry_id))
