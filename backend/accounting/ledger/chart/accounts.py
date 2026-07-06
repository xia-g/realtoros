"""Chart of Accounts definitions — minimal set for Phase 3.

Immutable reference data. account_code is the primary identifier.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountDef:
    code: str
    name: str
    acct_type: str
    parent: str | None = None


ACCOUNTS: list[AccountDef] = [
    AccountDef("01", "Основные средства", "asset"),
    AccountDef("02", "Амортизация ОС", "asset"),
    AccountDef("08", "Вложения во внеоборотные активы", "asset"),
    AccountDef("10", "Материалы", "asset"),
    AccountDef("19", "НДС по приобретённым ценностям", "asset"),
    AccountDef("20", "Основное производство", "asset"),
    AccountDef("26", "Общехозяйственные расходы", "expense"),
    AccountDef("44", "Расходы на продажу", "expense"),
    AccountDef("50", "Касса", "asset"),
    AccountDef("51", "Расчётные счета", "asset"),
    AccountDef("60", "Расчёты с поставщиками", "liability"),
    AccountDef("62", "Расчёты с покупателями", "asset"),
    AccountDef("68", "Расчёты по налогам и сборам", "liability"),
    AccountDef("69", "Расчёты по соц. страхованию", "liability"),
    AccountDef("70", "Расчёты с персоналом по оплате труда", "liability"),
    AccountDef("71", "Расчёты с подотчётными лицами", "asset"),
    AccountDef("76", "Расчёты с разными дебиторами/кредиторами", "asset"),
    AccountDef("90", "Продажи", "income"),
    AccountDef("90.01", "Выручка", "income", parent="90"),
    AccountDef("90.02", "Себестоимость продаж", "expense", parent="90"),
    AccountDef("90.03", "НДС", "expense", parent="90"),
    AccountDef("90.09", "Прибыль/убыток от продаж", "income", parent="90"),
    AccountDef("91", "Прочие доходы и расходы", "income"),
    AccountDef("99", "Прибыли и убытки", "income"),
]


def seed_sql() -> str:
    """Generate INSERT ... ON CONFLICT DO NOTHING SQL."""
    parts = []
    for a in ACCOUNTS:
        parent_val = f"'{a.parent}'" if a.parent else "NULL"
        parts.append(f"('{a.code}','{a.name}','{a.acct_type}',{parent_val})")
    vals = ",".join(parts)
    return f"""INSERT INTO accounting.chart_of_accounts (account_code, account_name, account_type, parent_code) VALUES {vals} ON CONFLICT (account_code) DO NOTHING;"""
