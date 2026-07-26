"""Stream 1 — Accounting repository (PostgreSQL)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from backend.services.accounting.models import (
    Account, AccountType, AccountingEntry, EntryLine, EntryStatus,
    ENTRY_TRANSITIONS, Journal, AccountingPeriod,
)


class AccountingRepository:
    """PostgreSQL repository for Accounting domain.

    Product Layer, not Platform.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(self._dsn)

    # ─── Accounts ────────────────────────────────────────────────

    def get_account(self, account_id: str) -> Account | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM accounts WHERE account_id = %s", (account_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return Account(
            account_id=str(row["account_id"]), code=str(row["code"]),
            name=str(row["name"]), account_type=AccountType(str(row["type"])),
            parent_id=str(row["parent_id"]) if row.get("parent_id") else None,
            is_active=bool(row["is_active"]),
        )

    def get_account_by_code(self, code: str) -> Account | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM accounts WHERE code = %s", (code,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return Account(
            account_id=str(row["account_id"]), code=str(row["code"]),
            name=str(row["name"]), account_type=AccountType(str(row["type"])),
            parent_id=str(row["parent_id"]) if row.get("parent_id") else None,
            is_active=bool(row["is_active"]),
        )

    def list_accounts(self) -> list[Account]:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM accounts ORDER BY code")
                rows = cur.fetchall()
        finally:
            conn.close()
        return [Account(
            account_id=str(r["account_id"]), code=str(r["code"]),
            name=str(r["name"]), account_type=AccountType(str(r["type"])),
            parent_id=str(r["parent_id"]) if r.get("parent_id") else None,
            is_active=bool(r["is_active"]),
        ) for r in rows]

    # ─── Periods ─────────────────────────────────────────────────

    def get_period(self, period_id: str) -> AccountingPeriod | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM accounting_periods WHERE period_id = %s", (period_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return AccountingPeriod(
            period_id=str(row["period_id"]), name=str(row["name"]),
            start_date=row["start_date"], end_date=row["end_date"],
            status=str(row["status"]),
        )

    def get_open_periods(self) -> list[AccountingPeriod]:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM accounting_periods WHERE status = 'OPEN' ORDER BY start_date")
                rows = cur.fetchall()
        finally:
            conn.close()
        return [AccountingPeriod(
            period_id=str(r["period_id"]), name=str(r["name"]),
            start_date=r["start_date"], end_date=r["end_date"],
            status=str(r["status"]),
        ) for r in rows]

    # ─── Journals ────────────────────────────────────────────────

    def get_journal(self, journal_id: str) -> Journal | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM journals WHERE journal_id = %s", (journal_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return Journal(
            journal_id=str(row["journal_id"]), name=str(row["name"]),
            journal_type=str(row["journal_type"]), period_id=str(row["period_id"]),
        )

    # ─── Entries ─────────────────────────────────────────────────

    def save_entry(self, entry: AccountingEntry) -> None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO accounting_entries
                        (entry_id, journal_id, document_id, period_id, entry_date,
                         description, status, created_at, posted_at, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (entry_id) DO UPDATE SET
                        journal_id = EXCLUDED.journal_id,
                        document_id = EXCLUDED.document_id,
                        period_id = EXCLUDED.period_id,
                        entry_date = EXCLUDED.entry_date,
                        description = EXCLUDED.description,
                        status = EXCLUDED.status,
                        posted_at = EXCLUDED.posted_at,
                        metadata = EXCLUDED.metadata
                """, (
                    entry.entry_id, entry.journal_id, entry.document_id,
                    entry.period_id, entry.entry_date, entry.description,
                    entry.status, entry.created_at or datetime.now(timezone.utc),
                    entry.posted_at,
                    psycopg2.extras.Json(entry.metadata),
                ))
                # Upsert lines
                for line in entry.lines:
                    cur.execute("""
                        INSERT INTO entry_lines
                            (line_id, entry_id, account_id, debit, credit, counterparty_id, description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (line_id) DO UPDATE SET
                            account_id = EXCLUDED.account_id,
                            debit = EXCLUDED.debit,
                            credit = EXCLUDED.credit,
                            counterparty_id = EXCLUDED.counterparty_id,
                            description = EXCLUDED.description
                    """, (
                        line.line_id, entry.entry_id, line.account_id,
                        str(line.debit), str(line.credit),
                        line.counterparty_id or "", line.description or "",
                    ))
            conn.commit()
        finally:
            conn.close()

    def get_entry(self, entry_id: str) -> AccountingEntry | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM accounting_entries WHERE entry_id = %s", (entry_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        entry = AccountingEntry(
            entry_id=str(row["entry_id"]), journal_id=str(row["journal_id"]),
            document_id=str(row["document_id"]), period_id=str(row["period_id"]),
            entry_date=row["entry_date"], description=str(row.get("description", "")),
            status=str(row["status"]),
            created_at=row.get("created_at"), posted_at=row.get("posted_at"),
            metadata=row.get("metadata") or {},
        )
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM entry_lines WHERE entry_id = %s ORDER BY line_id", (entry_id,))
                for r in cur.fetchall():
                    entry.lines.append(EntryLine(
                        line_id=str(r["line_id"]), entry_id=entry_id,
                        account_id=str(r["account_id"]),
                        debit=Decimal(str(r["debit"])),
                        credit=Decimal(str(r["credit"])),
                        counterparty_id=str(r["counterparty_id"]) if r.get("counterparty_id") else None,
                        description=str(r.get("description", "")),
                    ))
        finally:
            conn.close()
        return entry

    def list_entries(self, period_id: str | None = None,
                     document_id: str | None = None,
                     status: str | None = None,
                     limit: int = 50) -> list[AccountingEntry]:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = "SELECT entry_id FROM accounting_entries WHERE 1=1"
                params = []
                if period_id:
                    query += " AND period_id = %s"; params.append(period_id)
                if document_id:
                    query += " AND document_id = %s"; params.append(document_id)
                if status:
                    query += " AND status = %s"; params.append(status)
                query += " ORDER BY created_at DESC LIMIT %s"; params.append(limit)
                cur.execute(query, params)
                ids = [str(r["entry_id"]) for r in cur.fetchall()]
        finally:
            conn.close()
        return [self.get_entry(eid) for eid in ids if self.get_entry(eid)]

    def update_entry_status(self, entry_id: str, status: str,
                            posted_at: datetime | None = None) -> str | None:
        """Update entry status. Returns error message or None."""
        entry = self.get_entry(entry_id)
        if entry is None:
            return f"Entry not found: {entry_id}"

        allowed = ENTRY_TRANSITIONS.get(entry.status, [])
        if status not in allowed:
            return f"Transition {entry.status} → {status} not allowed"

        if status == "POSTED" and not entry.is_balanced:
            return f"Entry not balanced: debit={entry.total_debit}, credit={entry.total_credit}"

        conn = self._connect()
        try:
            with conn.cursor() as cur:
                if status == "POSTED":
                    cur.execute(
                        "UPDATE accounting_entries SET status = %s, posted_at = %s WHERE entry_id = %s",
                        (status, posted_at or datetime.now(timezone.utc), entry_id),
                    )
                else:
                    cur.execute(
                        "UPDATE accounting_entries SET status = %s WHERE entry_id = %s",
                        (status, entry_id),
                    )
            conn.commit()
        finally:
            conn.close()
        return None

    # ─── Ledger queries ──────────────────────────────────────────

    def get_account_turnover(self, account_id: str, period_id: str,
                             start_date: date | None = None,
                             end_date: date | None = None) -> dict:
        """Get debit/credit turnover for an account in a period."""
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = """
                    SELECT COALESCE(SUM(debit), 0) as total_debit,
                           COALESCE(SUM(credit), 0) as total_credit
                    FROM entry_lines el
                    JOIN accounting_entries ae ON el.entry_id = ae.entry_id
                    WHERE el.account_id = %s AND ae.period_id = %s
                    AND ae.status = 'POSTED'
                """
                params = [account_id, period_id]
                if start_date:
                    query += " AND ae.entry_date >= %s"; params.append(start_date)
                if end_date:
                    query += " AND ae.entry_date <= %s"; params.append(end_date)
                cur.execute(query, params)
                row = cur.fetchone()
        finally:
            conn.close()
        return {
            "account_id": account_id,
            "period_id": period_id,
            "debit": float(row["total_debit"]) if row else 0.0,
            "credit": float(row["total_credit"]) if row else 0.0,
        }

    def get_trial_balance(self, period_id: str) -> list[dict]:
        """Get trial balance for a period (all accounts with posted entries)."""
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT a.account_id, a.code, a.name, a.type,
                           COALESCE(SUM(el.debit), 0) as total_debit,
                           COALESCE(SUM(el.credit), 0) as total_credit
                    FROM accounts a
                    LEFT JOIN entry_lines el ON a.account_id = el.account_id
                    LEFT JOIN accounting_entries ae ON el.entry_id = ae.entry_id
                        AND ae.period_id = %s AND ae.status = 'POSTED'
                    GROUP BY a.account_id, a.code, a.name, a.type
                    ORDER BY a.code
                """, (period_id,))
                rows = cur.fetchall()
        finally:
            conn.close()
        return [{
            "account_id": str(r["account_id"]),
            "code": str(r["code"]),
            "name": str(r["name"]),
            "type": str(r["type"]),
            "debit": float(r["total_debit"]),
            "credit": float(r["total_credit"]),
            "balance": float(r["total_debit"]) - float(r["total_credit"]),
        } for r in rows]
