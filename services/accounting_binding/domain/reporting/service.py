"""
Domain — Reporting.

Построение отчётных проекций из JournalEntry.
Только rebuild из исходных данных. Никакой бизнес-логики.

Запрещено:
- report.adjust()
- report.update()
- любая не-идемпотентная модификация

Разрешено:
- rebuild(from journal_entry[])
- disposable: отчёт можно удалить и перестроить
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from contracts import JournalEntry


class ReportRepository(Protocol):
    """Интерфейс хранения отчётов (disposable)."""
    async def get_entries(self, company_id: str, from_date: date, to_date: date) -> list[JournalEntry]: ...
    async def rebuild_trial_balance(self, company_id: str, entries: list[JournalEntry]) -> None: ...
    async def clear_trial_balance(self, company_id: str) -> None: ...


@dataclass
class AccountBalance:
    """Остаток по счёту."""
    account_code: str
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal  # debit - credit


@dataclass
class TrialBalance:
    """Оборотно-сальдовая ведомость (disposable — можно удалить и перестроить)."""
    period_start: date
    period_end: date
    accounts: list[AccountBalance]
    total_debit: Decimal
    total_credit: Decimal
    generated_at: datetime


class ReportingService:
    """Построение отчётных проекций.

    Полностью пересчитываемые:
    - rebuild(from journal_entry) → TrialBalance
    - disposable: clear + rebuild
    """

    def __init__(self, repo: ReportRepository | None = None):
        self._repo = repo

    async def rebuild(
        self, company_id: str, from_date: date, to_date: date
    ) -> TrialBalance:
        """Полный rebuild отчёта из исходных JournalEntry.

        Disposable: старые данные удаляются, отчёт перестраивается.
        """
        if not self._repo:
            return TrialBalance(
                period_start=from_date, period_end=to_date,
                accounts=[], total_debit=Decimal("0"),
                total_credit=Decimal("0"), generated_at=datetime.utcnow(),
            )

        # 1. Clear old projection
        await self._repo.clear_trial_balance(company_id)

        # 2. Load raw data
        entries = await self._repo.get_entries(company_id, from_date, to_date)

        # 3. Aggregate (единственное место с бизнес-логикой отчёта)
        balances: dict[str, dict[str, Decimal]] = {}
        for entry in entries:
            for line in entry.lines:
                code = line.account_code
                if code not in balances:
                    balances[code] = {"debit": Decimal("0"), "credit": Decimal("0")}
                if line.side == "debit":
                    balances[code]["debit"] += line.amount
                else:
                    balances[code]["credit"] += line.amount

        accounts = [
            AccountBalance(
                account_code=code,
                debit_total=vals["debit"],
                credit_total=vals["credit"],
                balance=vals["debit"] - vals["credit"],
            )
            for code, vals in sorted(balances.items())
        ]

        tb = TrialBalance(
            period_start=from_date,
            period_end=to_date,
            accounts=accounts,
            total_debit=sum((a.debit_total for a in accounts), Decimal("0")),
            total_credit=sum((a.credit_total for a in accounts), Decimal("0")),
            generated_at=datetime.utcnow(),
        )

        # 4. Store rebuilt projection
        await self._repo.rebuild_trial_balance(company_id, entries)

        return tb
