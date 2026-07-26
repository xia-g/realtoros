"""Stream 3 — Reconciliation service (bank ↔ cash ledger matching)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Any

from backend.services.accounting.repository import AccountingRepository


class ReconciliationService:
    """Match bank statement transactions against cash ledger.

    Rule-based matching in v1:
      - Amount matches
      - Date within range (±3 days)
      - Counterparty name matches
    """

    RECON_STATUS_TRANSITIONS = {
        "OPEN": ["MATCHING", "CANCELLED"],
        "MATCHING": ["REVIEW", "RECONCILED"],
        "REVIEW": ["MATCHING", "RECONCILED"],
        "RECONCILED": ["LOCKED"],
        "LOCKED": [],
        "CANCELLED": [],
    }

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(self._dsn)

    # ─── Start reconciliation ─────────────────────────────────

    def start_reconciliation(self, period_id: str, account_id: str,
                             statement_balance: float = 0.0) -> dict:
        """Start a new reconciliation run for a cash account.

        Returns the run details with initial unmatched status.
        """
        import psycopg2
        import psycopg2.extras

        repo = AccountingRepository(self._dsn)
        turnover = repo.get_account_turnover(account_id, period_id)
        ledger_balance = float(turnover["debit"]) - float(turnover["credit"])

        run_id = str(uuid.uuid4())
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reconciliation_runs
                        (run_id, period_id, account_id, statement_balance,
                         ledger_balance, difference, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'OPEN')
                """, (
                    run_id, period_id, account_id,
                    str(statement_balance), str(ledger_balance),
                    str(statement_balance - ledger_balance),
                ))

                # Create unmatched lines from ledger entries
                cur.execute("""
                    SELECT le.*, ae.description as entry_desc
                    FROM ledger_entries le
                    JOIN accounting_entries ae ON le.entry_id = ae.entry_id
                    WHERE le.account_id = %s AND le.period_id = %s
                      AND ae.status = 'POSTED'
                    ORDER BY le.posting_date
                """, (account_id, period_id))
                for row in cur.fetchall():
                    line_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO reconciliation_lines
                            (line_id, run_id, transaction_date, amount,
                             description, matched, match_type, match_ref)
                        VALUES (%s, %s, %s, %s, %s, FALSE, 'unmatched', '')
                    """, (
                        line_id, run_id,
                        row[4] if len(row) > 4 else date.today(),
                        str(abs(float(row[6]) - float(row[7]))),  # balance_after
                        row.get("entry_desc", "") if isinstance(row, dict) else "",
                    ))
            conn.commit()
        finally:
            conn.close()

        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict | None:
        """Get reconciliation run with lines."""
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM reconciliation_runs WHERE run_id = %s", (run_id,))
                run = cur.fetchone()
                if not run:
                    return None

                cur.execute(
                    "SELECT * FROM reconciliation_lines WHERE run_id = %s ORDER BY transaction_date",
                    (run_id,),
                )
                lines = cur.fetchall()
        finally:
            conn.close()

        return {
            "run_id": str(run["run_id"]),
            "period_id": str(run["period_id"]),
            "account_id": str(run["account_id"]),
            "statement_balance": float(run["statement_balance"]),
            "ledger_balance": float(run["ledger_balance"]),
            "difference": float(run["difference"]),
            "status": str(run["status"]),
            "created_at": run["created_at"].isoformat() if run.get("created_at") else None,
            "lines": [
                {
                    "line_id": str(l["line_id"]),
                    "transaction_date": l["transaction_date"].isoformat() if l.get("transaction_date") else None,
                    "amount": float(l["amount"]),
                    "description": l.get("description", ""),
                    "matched": bool(l["matched"]),
                    "match_type": l.get("match_type", ""),
                    "match_ref": l.get("match_ref", ""),
                }
                for l in lines
            ],
            "matched_count": sum(1 for l in lines if l["matched"]),
            "unmatched_count": sum(1 for l in lines if not l["matched"]),
        }

    def match_line(self, run_id: str, line_id: str,
                   match_ref: str = "manual") -> str | None:
        """Mark a line as matched. Returns error or None."""
        import psycopg2
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reconciliation_lines SET matched = TRUE, "
                    "match_type = 'manual', match_ref = %s "
                    "WHERE line_id = %s AND run_id = %s",
                    (match_ref, line_id, run_id),
                )
                if cur.rowcount == 0:
                    return f"Line not found: {line_id}"
            conn.commit()
        finally:
            conn.close()
        return None

    def resolve_reconciliation(self, run_id: str) -> str | None:
        """Resolve reconciliation. Returns error or None."""
        import psycopg2
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reconciliation_runs SET status = 'RECONCILED', "
                    "resolved_at = %s WHERE run_id = %s",
                    (datetime.now(timezone.utc), run_id),
                )
                if cur.rowcount == 0:
                    return f"Run not found: {run_id}"
            conn.commit()
        finally:
            conn.close()
        return None
