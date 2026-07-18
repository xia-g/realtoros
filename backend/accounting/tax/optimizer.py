"""Tax Optimizer — tax scenario analysis and optimization suggestions.

Analyzes company tax regime, transaction history, and provides
recommendations for optimal tax strategy in specific situations.

Key scenarios:
- Municipal property purchase (VAT tax agent)
- USN vs OSNO comparison
- Patent + USN combination optimization
- Property tax (cadastral value based)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any


class TaxRegime(Enum):
    USN_INCOME = "usn_income"
    USN_INCOME_EXPENSE = "usn_income_expense"
    OSNO = "osno"
    PSN = "psn"
    USN_INCOME_EXPENSE_PSN = "usn_income_expense+psn"
    USN_INCOME_PSN = "usn_income+psn"


REGIME_RATES: dict[str, dict] = {
    "usn_income": {"rate": 0.06, "label": "УСН «Доходы» 6%"},
    "usn_income_expense": {"rate": 0.15, "label": "УСН «Доходы минус Расходы» 15%"},
    "osno": {"rate": 0.20, "label": "ОСНО 20% (налог на прибыль)"},
    "psn": {"rate": 0.06, "label": "Патент (ПСН) 6% от вменённого дохода"},
}


@dataclass
class TaxScenario:
    name: str
    description: str
    tax_amount: Decimal
    effective_rate: float
    vat_impact: Decimal | None = None
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high


@dataclass
class OptimizationResult:
    company_name: str
    current_regime: str
    scenarios: list[TaxScenario]
    recommended: TaxScenario | None
    recommendations: list[str]
    warnings: list[str]
    next_deadlines: list[dict]


# ── Helpers ──

VAT_RATE = Decimal("0.20")  # 20% standard VAT
VAT_RATE_REDUCED = Decimal("0.10")  # 10% for some goods
USN_EXPENSE_RATE = Decimal("0.15")
USN_INCOME_RATE = Decimal("0.06")
INSURANCE_RATE = Decimal("0.153")  # 15.3% for IP insurance contributions
PROPERTY_TAX_RATE = Decimal("0.02")  # 2% of cadastral value (commercial)


def parse_regime(regime_str: str) -> list[TaxRegime]:
    """Parse combined regime string into list of regimes."""
    parts = regime_str.split("+")
    regimes = []
    for p in parts:
        try:
            regimes.append(TaxRegime(p.strip()))
        except ValueError:
            regimes.append(TaxRegime.USN_INCOME_EXPENSE)
    return regimes


def calculate_vat_tax_agent(property_price: Decimal) -> Decimal:
    """Calculate VAT that must be withheld as tax agent."""
    # VAT = price × 20/120 (when price includes VAT)
    return (property_price * VAT_RATE) / (Decimal("1") + VAT_RATE)


def calculate_vat_as_taxpayer(revenue: Decimal, expenses: Decimal) -> Decimal:
    """Calculate VAT payable as taxpayer (OSNO)."""
    vat_out = revenue * VAT_RATE / (Decimal("1") + VAT_RATE)
    vat_in = expenses * VAT_RATE / (Decimal("1") + VAT_RATE)
    return max(Decimal("0"), vat_out - vat_in)


def calculate_usn_tax(
    income: Decimal,
    expenses: Decimal,
    regime: TaxRegime,
    patents: dict[str, Decimal] | None = None,
) -> Decimal:
    """Calculate USN tax."""
    if regime == TaxRegime.USN_INCOME:
        tax = income * USN_INCOME_RATE
        # Can reduce by insurance premiums (50% max)
        return max(tax * Decimal("0.5"), Decimal("0"))

    elif regime == TaxRegime.USN_INCOME_EXPENSE:
        # 15% of (income - expenses), min 1% of income
        base = max(income - expenses, Decimal("0"))
        tax = base * USN_EXPENSE_RATE
        min_tax = income * Decimal("0.01")
        return max(tax, min_tax)

    elif "+" in regime.value:
        # Combined: USN + Patent
        total = Decimal("0")
        usn_regime = regime.value.split("+")[0]
        if usn_regime == "usn_income":
            total += max(income * USN_INCOME_RATE * Decimal("0.5"), Decimal("0"))
        else:
            total += max(
                max(income - expenses, Decimal("0")) * USN_EXPENSE_RATE,
                income * Decimal("0.01"),
            )
        # Patent amount is fixed (add later)
        if patents:
            total += sum(patents.values())
        return total

    return Decimal("0")


# ── Main Optimizer ──


class TaxOptimizer:
    """Analyze tax situation and suggest optimal strategy."""

    def __init__(self, pool=None):
        self.pool = pool

    async def analyze_property_purchase(
        self,
        company_id: str,
        company_name: str,
        regime: str,
        property_price: Decimal,
        cadastral_value: Decimal | None = None,
        annual_income: Decimal = Decimal("0"),
        annual_expenses: Decimal = Decimal("0"),
        is_municipal: bool = True,
    ) -> OptimizationResult:
        """Analyze tax implications of commercial property purchase."""
        regimes = parse_regime(regime)
        warnings: list[str] = []
        recommendations: list[str] = []
        scenarios: list[TaxScenario] = []

        vat_in_price = calculate_vat_tax_agent(property_price)

        # ── Scenario 1: Current regime (USN D-R + Patent) ──
        if is_municipal:
            warnings.append(
                "Покупка муниципального имущества: вы — налоговый агент по НДС. "
                "Обязаны исчислить, удержать и уплатить НДС в бюджет."
            )

            vat_agent_scenario = TaxScenario(
                name="Текущий режим + НДС как налоговый агент",
                description=(
                    f"ИП на УСН + Патент. Покупка помещения за {property_price:,.0f}₽.\n"
                    f"НДС как налоговый агент: {vat_in_price:,.0f}₽ (20/120 от цены).\n"
                    f"Вся стоимость помещения → расходы по УСН."
                ),
                tax_amount=vat_in_price,  # VAT to pay as agent
                effective_rate=float(vat_in_price / property_price * 100),
                vat_impact=vat_in_price,
                pros=[
                    "Вся стоимость помещения (с НДС) включается в расходы УСН",
                    "Помещение → основное средство, стоимость списывается постепенно",
                    "При УСН Д-Р ставка 15% от разницы доходов и расходов",
                ],
                cons=[
                    "НДС нужно уплатить в бюджет как налоговому агенту до 25 числа",
                    "УСН не даёт права на вычет входного НДС",
                    "Нужно подать налоговую декларацию по НДС (электронно)",
                ],
                risk_level="medium",
            )
            scenarios.append(vat_agent_scenario)

            recommendations.append(
                "🇷🇺 **НДС как налоговый агент**: "
                "Подайте декларацию по НДС (электронно) до 25 числа месяца, "
                "следующего за кварталом покупки. Уплатите НДС в тот же срок."
            )

        # ── Scenario 2: Switch to OSNO for VAT deduction ──
        usn_tax = calculate_usn_tax(annual_income, annual_expenses, regimes[0])
        osno_profit_tax = max(
            (annual_income - annual_expenses - property_price) * Decimal("0.20"),
            Decimal("0"),
        )
        osno_vat = calculate_vat_as_taxpayer(annual_income, annual_expenses + property_price)

        # Compare USN + VAT agent vs OSNO
        total_usn_burden = usn_tax + vat_in_price
        total_osno_burden = osno_profit_tax + osno_vat

        if total_osno_burden < total_usn_burden:
            scenarios.append(
                TaxScenario(
                    name="Переход на ОСНО (выгоднее по налогам)",
                    description=(
                        f"ОСНО: налог на прибыль ≈ {osno_profit_tax:,.0f}₽, "
                        f"НДС к уплате ≈ {osno_vat:,.0f}₽\n"
                        f"Итого: {total_osno_burden:,.0f}₽ vs УСН: {total_usn_burden:,.0f}₽"
                    ),
                    tax_amount=total_osno_burden,
                    effective_rate=float(total_osno_burden / max(annual_income, Decimal("1")) * 100),
                    vat_impact=osno_vat,
                    pros=[
                        "Можно принять НДС к вычету (входной НДС со стоимости помещения)",
                        "Налог на прибыль учитывает все расходы",
                        "Больше контрагентов на ОСНО",
                    ],
                    cons=[
                        "Сложнее отчётность (НДС + налог на прибыль)",
                        "Нужно вести полноценный бухучёт",
                        "Потеря права на патент",
                        "Уведомление о переходе — до 15 января",
                    ],
                    risk_level="medium",
                )
            )
            recommendations.append(
                "💡 **Переход на ОСНО может быть выгоднее**: "
                f"экономия ~{(total_usn_burden - total_osno_burden):,.0f}₽ в год. "
                "Учтите что это решение на весь календарный год."
            )
        else:
            scenarios.append(
                TaxScenario(
                    name="Остаться на УСН + Патент (рекомендуется)",
                    description=(
                        f"УСН Д-Р: налог ≈ {usn_tax:,.0f}₽\n"
                        f"НДС как агент: {vat_in_price:,.0f}₽\n"
                        f"Итого: {total_usn_burden:,.0f}₽"
                    ),
                    tax_amount=total_usn_burden,
                    effective_rate=float(total_usn_burden / max(annual_income, Decimal("1")) * 100),
                    vat_impact=vat_in_price,
                    pros=[
                        "Меньше отчётности (одна декларация УСН)",
                        "Можно совмещать с патентом",
                        "Проще администрирование",
                    ],
                    cons=[
                        "Нет вычета НДС (но это не критично для УСН)",
                        "Нужна электронная декларация по НДС как агенту",
                    ],
                    risk_level="low",
                )
            )
            recommendations.append(
                "✅ **Остаться на УСН + Патент**: "
                "Текущий режим оптимален. Единственное доп. обязательство — "
                "уплатить НДС как налоговому агенту."
            )

        # ── Scenario 3: Property tax implications ──
        if cadastral_value and cadastral_value > 0:
            annual_property_tax = cadastral_value * PROPERTY_TAX_RATE
            scenarios.append(
                TaxScenario(
                    name="Налог на имущество (если применимо)",
                    description=(
                        f"Кадастровая стоимость: {cadastral_value:,.0f}₽\n"
                        f"Ежегодный налог на имущество: {annual_property_tax:,.0f}₽ "
                        f"(2% от кадастровой стоимости)"
                    ),
                    tax_amount=annual_property_tax,
                    effective_rate=2.0,
                    pros=[
                        "При УСН налог на имущество платят только по коммерческой недвижимости",
                        "Можно оспорить кадастровую стоимость если она завышена",
                    ],
                    cons=[
                        "Налог начисляется ежегодно вне зависимости от доходов",
                    ],
                    risk_level="low",
                )
            )
            recommendations.append(
                f"🏢 **Налог на имущество**: ~{annual_property_tax:,.0f}₽ в год. "
                "Платится ежегодно до 1 декабря. Рекомендуется проверить кадастровую стоимость."
            )

        # ── Next deadlines ──
        next_deadlines = [
            {
                "title": "Уплата НДС как налогового агента (покупка помещения)",
                "description": f"Сумма: {vat_in_price:,.0f}₽",
                "deadline": self._next_vat_deadline(),
                "type": "vat_agent",
            },
            {
                "title": "Декларация по НДС (электронно)",
                "description": "Подать в ФНС через ТКС до 25 числа",
                "deadline": self._next_vat_deadline(),
                "type": "vat_declaration",
            },
            {
                "title": "УСН — авансовый платёж за квартал",
                "description": "До 25 числа месяца после квартала",
                "deadline": self._next_usn_deadline(),
                "type": "usn_advance",
            },
        ]

        # Determine recommendation
        recommended = min(scenarios, key=lambda s: s.tax_amount) if scenarios else None

        return OptimizationResult(
            company_name=company_name,
            current_regime=regime,
            scenarios=scenarios,
            recommended=recommended,
            recommendations=recommendations,
            warnings=warnings,
            next_deadlines=next_deadlines,
        )

    def _next_vat_deadline(self) -> str:
        """Next VAT deadline (25th of month after quarter)."""
        from datetime import date, timedelta
        today = date.today()
        q_end_months = {3: 3, 6: 6, 9: 9, 12: 12}
        current_q = ((today.month - 1) // 3) + 1
        q_end_month = current_q * 3
        deadline_month = q_end_month
        deadline_year = today.year
        if today.month > deadline_month:
            deadline_month += 3
            if deadline_month > 12:
                deadline_month = 3
                deadline_year += 1
        return f"{deadline_year:04d}-{deadline_month:02d}-25"

    def _next_usn_deadline(self) -> str:
        """Next USN advance payment deadline (25th after quarter)."""
        from datetime import date
        today = date.today()
        current_q = ((today.month - 1) // 3) + 1
        deadline_month = current_q * 3 + 1
        deadline_year = today.year
        if deadline_month > 12:
            deadline_month = deadline_month - 12
            deadline_year += 1
        return f"{deadline_year:04d}-{deadline_month:02d}-25"

    async def get_optimization_tips(
        self, company_id: str, regime: str
    ) -> list[str]:
        """Get generic optimization tips for a company."""
        tips = []
        regimes = parse_regime(regime)

        if TaxRegime.USN_INCOME in regimes or TaxRegime.USN_INCOME_EXPENSE in regimes:
            tips.append(
                "📉 **Уменьшение УСН**: Уменьшайте налог на сумму страховых взносов "
                "(до 50% для УСН Доходы, 100% для УСН Доходы-Расходы)."
            )
            tips.append(
                "📊 **Раздельный учёт**: При совмещении УСН + Патент ведите раздельный "
                "учёт доходов и расходов по каждому режиму."
            )

        if TaxRegime.USN_INCOME_EXPENSE in regimes:
            tips.append(
                "🏗 **Капитальные расходы**: Стоимость ОС (включая недвижимость) "
                "списывается равными долями в течение налогового периода."
            )

        tips.append(
            "📋 **Электронная отчётность**: При покупке муниципального имущества "
            "декларацию по НДС подают только электронно через оператора ЭДО."
        )

        return tips
