"""Stream 3 — Reporting service (computed financial views)."""
from __future__ import annotations

from decimal import Decimal

from backend.services.accounting.repository import AccountingRepository


class ReportingService:
    """Computed financial reports from ledger data.

    All reports are computed — never stored as source of truth.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _repo(self) -> AccountingRepository:
        return AccountingRepository(self._dsn)

    def get_trial_balance(self, period_id: str) -> dict:
        """Trial balance with totals verification."""
        repo = self._repo()
        accounts = repo.get_trial_balance(period_id)
        total_debit = sum(a["debit"] for a in accounts)
        total_credit = sum(a["credit"] for a in accounts)
        return {
            "period_id": period_id,
            "accounts": accounts,
            "totals": {
                "debit": total_debit,
                "credit": total_credit,
                "difference": total_debit - total_credit,
                "is_balanced": abs(total_debit - total_credit) < 0.01,
            },
        }

    def get_balance_sheet(self, period_id: str) -> dict:
        """Balance sheet with asset/liability/equity sections."""
        repo = self._repo()
        all_accounts = repo.get_trial_balance(period_id)

        sections = {
            "asset": {"name": "Assets", "accounts": [], "total": 0.0},
            "liability": {"name": "Liabilities", "accounts": [], "total": 0.0},
            "equity": {"name": "Equity", "accounts": [], "total": 0.0},
        }

        for a in all_accounts:
            atype = a["type"]
            if atype in sections:
                balance = abs(a["balance"])
                sections[atype]["accounts"].append({
                    "code": a["code"], "name": a["name"],
                    "balance": balance, "account_id": a["account_id"],
                })
                sections[atype]["total"] += balance

        total_assets = sections["asset"]["total"]
        total_liabilities_equity = sections["liability"]["total"] + sections["equity"]["total"]

        return {
            "period_id": period_id,
            "sections": [sections[k] for k in ["asset", "liability", "equity"]],
            "total_assets": total_assets,
            "total_liabilities_equity": total_liabilities_equity,
            "is_balanced": abs(total_assets - total_liabilities_equity) < 0.01,
        }

    def get_profit_loss(self, period_id: str) -> dict:
        """Profit & loss with net income computation."""
        repo = self._repo()
        all_accounts = repo.get_trial_balance(period_id)

        sections = {
            "revenue": {"name": "Revenue", "accounts": [], "total": 0.0},
            "expense": {"name": "Expenses", "accounts": [], "total": 0.0},
        }

        for a in all_accounts:
            atype = a["type"]
            if atype in sections:
                balance = abs(a["balance"])
                sections[atype]["accounts"].append({
                    "code": a["code"], "name": a["name"],
                    "balance": balance, "account_id": a["account_id"],
                })
                sections[atype]["total"] += balance

        total_revenue = sections["revenue"]["total"]
        total_expenses = sections["expense"]["total"]
        net_income = total_revenue - total_expenses

        return {
            "period_id": period_id,
            "sections": [sections[k] for k in ["revenue", "expense"]],
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "net_income": net_income,
        }
