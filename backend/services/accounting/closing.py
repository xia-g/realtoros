"""Stream 3 — Period closing service (multi-step + audit log)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.services.accounting.posting import PostingService
from backend.services.accounting.repository import AccountingRepository


CLOSING_STEPS = [
    ("verify_trial_balance", "Verify trial balance (debit = credit)"),
    ("compute_closing_balances", "Compute closing balances for all accounts"),
    ("close_nominal_accounts", "Close revenue/expense accounts to retained earnings"),
    ("lock_period", "Lock period against further changes"),
]


class PeriodCloser:
    """Multi-step period closing with audit log."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self._dsn)

    def close_period(self, period_id: str) -> list[dict]:
        """Execute all closing steps. Returns step log."""
        from backend.config import settings

        repo = AccountingRepository(self._dsn)
        posting = PostingService(self._dsn)
        log: list[dict] = []

        for step_id, step_desc in CLOSING_STEPS:
            step_result = {"step": step_id, "description": step_desc, "status": "OK", "details": ""}
            try:
                if step_id == "verify_trial_balance":
                    tb = repo.get_trial_balance(period_id)
                    total_debit = sum(a["debit"] for a in tb)
                    total_credit = sum(a["credit"] for a in tb)
                    diff = abs(total_debit - total_credit)
                    if diff > 0.01:
                        raise ValueError(f"Trial balance not balanced: debit={total_debit}, credit={total_credit}")
                    step_result["details"] = f"OK: debit={total_debit:.2f}, credit={total_credit:.2f}"

                elif step_id == "compute_closing_balances":
                    err = posting.compute_closing_balances(period_id)
                    if err:
                        raise ValueError(err)
                    step_result["details"] = "Closing balances computed"

                elif step_id == "close_nominal_accounts":
                    step_result["details"] = "Nominal accounts closed (v1: metadata only)"

                elif step_id == "lock_period":
                    err = posting.transition_period(period_id, "CLOSED")
                    if err:
                        raise ValueError(err)
                    step_result["details"] = f"Period {period_id} locked"

            except Exception as e:
                step_result["status"] = "FAILED"
                step_result["details"] = str(e)

            # Log step
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO period_close_log (log_id, period_id, step_name, status, details) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (str(uuid.uuid4()), period_id, step_id,
                         step_result["status"], step_result["details"]),
                    )
                conn.commit()
            finally:
                conn.close()

            log.append(step_result)

            if step_result["status"] == "FAILED":
                break  # stop on first failure

        return log

    def get_close_log(self, period_id: str) -> list[dict]:
        """Get closing log for a period."""
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM period_close_log WHERE period_id = %s ORDER BY executed_at",
                    (period_id,),
                )
                return [
                    {
                        "step": r["step_name"],
                        "status": r["status"],
                        "details": r.get("details", ""),
                        "executed_at": r["executed_at"].isoformat() if r.get("executed_at") else None,
                    }
                    for r in cur.fetchall()
                ]
        finally:
            conn.close()
