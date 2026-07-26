"""Stream 2 — Posting Service (Journal + Ledger + Period Management)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from backend.services.accounting.models import (
    Account, AccountType, AccountingEntry, EntryStatus, ENTRY_TRANSITIONS,
)
from backend.services.accounting.repository import AccountingRepository


class PostingError(Exception):
    pass


class PostingService:
    """Post validated entries to the ledger.

    Creates JournalEntry, LedgerEntry records, and updates balances.
    All operations are atomic within a single transaction.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._repo = AccountingRepository(dsn)

    def _connect(self):
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(self._dsn)

    # ─── Journal Sequence ───────────────────────────────────────

    def _next_sequence(self, period_id: str) -> int:
        import psycopg2
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO journal_sequences (period_id, last_sequence) "
                    "VALUES (%s, 1) "
                    "ON CONFLICT (period_id) DO UPDATE SET last_sequence = journal_sequences.last_sequence + 1 "
                    "RETURNING last_sequence",
                    (period_id,),
                )
                row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        return int(row[0]) if row else 1

    # ─── Period validation ──────────────────────────────────────

    def _check_period_open(self, period_id: str) -> None:
        period = self._repo.get_period(period_id)
        if period is None:
            raise PostingError(f"Period not found: {period_id}")
        if period.status != "OPEN":
            raise PostingError(f"Period '{period.name}' is {period.status}, not OPEN")

    # ─── Ledger running balance ─────────────────────────────────

    def _get_latest_balance(self, account_id: str,
                            period_id: str) -> Decimal:
        """Get the latest balance_after for an account in a period."""
        import psycopg2
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT balance_after FROM ledger_entries "
                    "WHERE account_id = %s AND period_id = %s "
                    "ORDER BY posting_date DESC, ledger_entry_id DESC LIMIT 1",
                    (account_id, period_id),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        return Decimal(str(row[0])) if row else Decimal("0")

    def _get_account_type(self, account_id: str) -> AccountType:
        account = self._repo.get_account(account_id)
        if account is None:
            return AccountType.ASSET
        return account.account_type

    # ─── Post entry ─────────────────────────────────────────────

    def post_entry(self, entry_id: str, force: bool = False) -> str | None:
        """Post an entry to the ledger. Returns error message or None.

        Creates:
          - JournalEntry (with sequence number)
          - LedgerEntry per line (with running balance)
          - AccountBalances updated

        All in one atomic transaction.
        """
        import psycopg2
        import psycopg2.extras

        entry = self._repo.get_entry(entry_id)
        if entry is None:
            return f"Entry not found: {entry_id}"

        if entry.status != "VALIDATED" and not force:
            return f"Only VALIDATED entries can be posted (current: {entry.status})"

        if not entry.is_balanced:
            return f"Entry not balanced: debit={entry.total_debit}, credit={entry.total_credit}"

        # Check period is open
        try:
            self._check_period_open(entry.period_id)
        except PostingError as e:
            return str(e)

        conn = self._connect()
        try:
            with conn.cursor() as cur:
                # 1. Get sequence number
                cur.execute(
                    "INSERT INTO journal_sequences (period_id, last_sequence) "
                    "VALUES (%s, 1) "
                    "ON CONFLICT (period_id) DO UPDATE SET last_sequence = journal_sequences.last_sequence + 1 "
                    "RETURNING last_sequence",
                    (entry.period_id,),
                )
                seq = int(cur.fetchone()[0])

                # 2. Create journal entry
                je_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO journal_entries (journal_entry_id, journal_id, entry_id, "
                    "posting_date, period_id, sequence_number) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (je_id, entry.journal_id, entry.entry_id,
                     entry.entry_date, entry.period_id, seq),
                )

                # 3. Create ledger entries with running balance
                now = entry.entry_date or date.today()
                for line in entry.lines:
                    # Get current balance
                    cur.execute(
                        "SELECT balance_after FROM ledger_entries "
                        "WHERE account_id = %s AND period_id = %s "
                        "ORDER BY posting_date DESC, ledger_entry_id DESC LIMIT 1",
                        (line.account_id, entry.period_id),
                    )
                    row = cur.fetchone()
                    current_balance = Decimal(str(row[0])) if row else Decimal("0")

                    balance_after = current_balance + line.debit - line.credit

                    le_id = str(uuid.uuid4())
                    cur.execute(
                        "INSERT INTO ledger_entries "
                        "(ledger_entry_id, account_id, entry_id, period_id, posting_date, "
                        "debit, credit, balance_after, description) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (le_id, line.account_id, entry.entry_id, entry.period_id,
                         now, str(line.debit), str(line.credit),
                         str(balance_after), line.description or ""),
                    )

                # 4. Update or create account balances
                for line in entry.lines:
                    cur.execute("""
                        INSERT INTO account_balances
                            (account_id, period_id, opening_debit, opening_credit,
                             turnover_debit, turnover_credit, closing_debit, closing_credit)
                        VALUES (%s, %s, 0, 0, %s, %s, %s, %s)
                        ON CONFLICT (account_id, period_id) DO UPDATE SET
                            turnover_debit = account_balances.turnover_debit + %s,
                            turnover_credit = account_balances.turnover_credit + %s
                    """, (
                        line.account_id, entry.period_id,
                        str(line.debit), str(line.credit),
                        str(line.debit), str(line.credit),
                        str(line.debit), str(line.credit),
                    ))

                # 5. Update entry status to POSTED
                now_dt = datetime.now(timezone.utc)
                cur.execute(
                    "UPDATE accounting_entries SET status = %s, posted_at = %s WHERE entry_id = %s",
                    ("POSTED", now_dt, entry.entry_id),
                )

            conn.commit()
        except Exception as e:
            conn.rollback()
            return f"Posting failed (rolled back): {e}"
        finally:
            conn.close()

        return None

    # ─── Period Management ──────────────────────────────────────

    PERIOD_TRANSITIONS = {
        "OPEN": ["CLOSING", "LOCKED"],
        "CLOSING": ["CLOSED", "OPEN"],
        "CLOSED": ["LOCKED"],
        "LOCKED": [],
    }

    def transition_period(self, period_id: str, target: str) -> str | None:
        """Transition period to target state. Returns error or None."""
        period = self._repo.get_period(period_id)
        if period is None:
            return f"Period not found: {period_id}"

        allowed = self.PERIOD_TRANSITIONS.get(period.status, [])
        if target not in allowed:
            return f"Period transition {period.status} → {target} not allowed"

        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE accounting_periods SET status = %s WHERE period_id = %s",
                    (target, period_id),
                )
            conn.commit()
        finally:
            conn.close()
        return None

    # ─── Balance closing computation ────────────────────────────

    def compute_closing_balances(self, period_id: str) -> str | None:
        """Compute closing balances for all accounts in a period.

        closing = opening + turnover (accounted for account type)
        """
        period = self._repo.get_period(period_id)
        if period is None:
            return f"Period not found: {period_id}"

        accounts = self._repo.list_accounts()

        conn = self._connect()
        try:
            with conn.cursor() as cur:
                for account in accounts:
                    # Get opening balance from previous period
                    opening_debit = Decimal("0")
                    opening_credit = Decimal("0")

                    # Get turnover from current period
                    turnover = self._repo.get_account_turnover(
                        account.account_id, period_id,
                    )

                    t_debit = Decimal(str(turnover["debit"]))
                    t_credit = Decimal(str(turnover["credit"]))

                    # Compute closing balance
                    net = opening_debit - opening_credit + t_debit - t_credit

                    if account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
                        c_debit = net if net > 0 else Decimal("0")
                        c_credit = abs(net) if net < 0 else Decimal("0")
                    else:
                        c_credit = net if net > 0 else Decimal("0")
                        c_debit = abs(net) if net < 0 else Decimal("0")

                    cur.execute("""
                        INSERT INTO account_balances
                            (account_id, period_id, opening_debit, opening_credit,
                             turnover_debit, turnover_credit, closing_debit, closing_credit)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (account_id, period_id) DO UPDATE SET
                            opening_debit = EXCLUDED.opening_debit,
                            opening_credit = EXCLUDED.opening_credit,
                            turnover_debit = EXCLUDED.turnover_debit,
                            turnover_credit = EXCLUDED.turnover_credit,
                            closing_debit = EXCLUDED.closing_debit,
                            closing_credit = EXCLUDED.closing_credit
                    """, (
                        account.account_id, period_id,
                        str(opening_debit), str(opening_credit),
                        str(t_debit), str(t_credit),
                        str(c_debit), str(c_credit),
                    ))
            conn.commit()
        finally:
            conn.close()
        return None

    # ─── Balance queries ────────────────────────────────────────

    def get_balance_sheet(self, period_id: str) -> list[dict]:
        """Get balance sheet (assets = liabilities + equity)."""
        balances = self._repo.get_trial_balance(period_id)
        return [
            b for b in balances
            if b["type"] in ("asset", "liability", "equity")
        ]

    def get_profit_loss(self, period_id: str) -> list[dict]:
        """Get profit & loss (revenue - expense)."""
        balances = self._repo.get_trial_balance(period_id)
        return [
            b for b in balances
            if b["type"] in ("revenue", "expense")
        ]
