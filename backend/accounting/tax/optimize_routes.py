"""Tax optimization API — scenario analysis and recommendations.

POST /tax/optimize/property — analyze property purchase tax implications
GET  /tax/optimize/tips — get generic optimization tips for a company
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException

from backend.accounting.db.pool import get_pool
from backend.accounting.tax.optimizer import TaxOptimizer

router = APIRouter(prefix="/tax/optimize", tags=["Tax Optimization"])


@router.post("/property")
async def analyze_property_purchase(body: dict):
    """Analyze tax implications of a commercial property purchase.

    Args:
        company_id: UUID of the company
        property_price: Purchase price in RUB
        cadastral_value: Optional cadastral value for property tax calc
        annual_income: Estimated annual income (for regime comparison)
        annual_expenses: Estimated annual expenses
        is_municipal: Whether buying from municipality (VAT agent)
    """
    required = ["company_id", "property_price"]
    for field in required:
        if field not in body:
            raise HTTPException(400, f"Missing required field: {field}")

    pool = await get_pool()

    # Get company info
    async with pool.acquire() as conn:
        company = await conn.fetchrow(
            "SELECT id, name, inn, tax_regime FROM public.companies WHERE id = $1",
            body["company_id"],
        )
        if not company:
            raise HTTPException(404, "Company not found")

    optimizer = TaxOptimizer(pool)
    result = await optimizer.analyze_property_purchase(
        company_id=str(company["id"]),
        company_name=company["name"],
        regime=company["tax_regime"],
        property_price=Decimal(str(body["property_price"])),
        cadastral_value=Decimal(str(body.get("cadastral_value", 0))),
        annual_income=Decimal(str(body.get("annual_income", 0))),
        annual_expenses=Decimal(str(body.get("annual_expenses", 0))),
        is_municipal=body.get("is_municipal", True),
    )

    return {
        "company_name": result.company_name,
        "current_regime": result.current_regime,
        "scenarios": [
            {
                "name": s.name,
                "description": s.description,
                "tax_amount": str(s.tax_amount),
                "effective_rate": round(s.effective_rate, 1),
                "vat_impact": str(s.vat_impact) if s.vat_impact else None,
                "pros": s.pros,
                "cons": s.cons,
                "risk_level": s.risk_level,
            }
            for s in result.scenarios
        ],
        "recommended": {
            "name": result.recommended.name,
            "tax_amount": str(result.recommended.tax_amount),
        } if result.recommended else None,
        "recommendations": result.recommendations,
        "warnings": result.warnings,
        "next_deadlines": result.next_deadlines,
    }


@router.get("/tips")
async def get_optimization_tips(company_id: str):
    """Get generic tax optimization tips for a company."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        company = await conn.fetchrow(
            "SELECT id, name, tax_regime FROM public.companies WHERE id = $1",
            company_id,
        )
        if not company:
            raise HTTPException(404, "Company not found")

    optimizer = TaxOptimizer()
    tips = await optimizer.get_optimization_tips(
        company_id=company_id,
        regime=company["tax_regime"],
    )

    # Also get regime info
    from backend.accounting.tax.optimizer import REGIME_RATES, parse_regime
    regimes = parse_regime(company["tax_regime"])
    regime_info = [
        REGIME_RATES.get(r.value, {"label": r.value})
        for r in regimes
    ]

    return {
        "company_name": company["name"],
        "tax_regime": company["tax_regime"],
        "regime_details": regime_info,
        "tips": tips,
    }
