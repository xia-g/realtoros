"""Seed obligations for IP Shulgina's real-life scenario.

Scenario: IP Shulgina bought commercial property from the city.
- Purchase price: ~5,000,000 RUB (example)
- Tax regime: USN Income-Expenses + Patent
- VAT agent for municipal purchase
"""

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

from backend.accounting.db.pool import get_pool


async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get IP Shulgina
        ip = await conn.fetchrow(
            "SELECT id, name, inn FROM public.companies WHERE inn = '780527855675'"
        )
        if not ip:
            print("❌ IP Shulgina not found in DB")
            return

        cid = ip["id"]
        print(f"✅ Company: {ip['name']} (ID: {cid})")

        # Check if obligations already exist
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM public.obligations WHERE company_id = $1", cid
        )
        if existing and existing > 0:
            print(f"⚠️  {existing} obligations already exist — skipping seed")
            return

        # Create obligations for the property purchase scenario
        # Assume property price = 5,000,000 RUB
        price = Decimal("5000000")
        vat_amount = (price * Decimal("0.20")) / Decimal("1.20")  # 833,333 RUB

        obligations = [
            {
                "company_id": cid,
                "obligation_type": "vat_payable",
                "title": "НДС как налоговый агент — покупка помещения у города",
                "description": (
                    f"При покупке муниципального имущества (помещение {price:,.0f}₽) "
                    f"необходимо исчислить и уплатить НДС как налоговый агент. "
                    f"Сумма НДС: {vat_amount:,.0f}₽ (20/120 от цены). "
                    "Декларация подаётся электронно."
                ),
                "amount": vat_amount,
                "due_date": _next_quarter_25(),
                "status": "pending",
                "recurrence": "one_time",
                "reminder_days": 14,
                "notes": "Обязательно подать электронную декларацию по НДС через ТКС",
            },
            {
                "company_id": cid,
                "obligation_type": "tax_usn",
                "title": "УСН (Доходы минус Расходы) — авансовый платёж",
                "description": (
                    "Ежеквартальный авансовый платёж по УСН. "
                    "Ставка 15% от разницы доходов и расходов. "
                    "Минимальный налог: 1% от доходов."
                ),
                "amount": Decimal("75000"),
                "due_date": _next_quarter_25(),
                "status": "pending",
                "recurrence": "quarterly",
                "reminder_days": 10,
                "notes": "Уменьшайте налог на сумму страховых взносов",
            },
            {
                "company_id": cid,
                "obligation_type": "insurance",
                "title": "Страховые взносы ИП (фиксированные)",
                "description": (
                    "Фиксированные страховые взносы ИП. "
                    "Пенсионное + медицинское страхование."
                ),
                "amount": Decimal("50000"),
                "due_date": date(date.today().year, 12, 31),
                "status": "pending",
                "recurrence": "yearly",
                "reminder_days": 30,
                "notes": "Можно платить частями ежеквартально для уменьшения УСН",
            },
            {
                "company_id": cid,
                "obligation_type": "tax_property",
                "title": "Налог на имущество (коммерческое помещение)",
                "description": (
                    "Налог на коммерческую недвижимость. "
                    "Исчисляется от кадастровой стоимости. "
                    "Ставка до 2%."
                ),
                "amount": Decimal("100000"),
                "due_date": date(date.today().year, 12, 1),
                "status": "pending",
                "recurrence": "yearly",
                "reminder_days": 30,
                "notes": "Проверьте кадастровую стоимость — её можно оспорить",
            },
            {
                "company_id": cid,
                "obligation_type": "other",
                "title": "Подача декларации по НДС (электронно)",
                "description": (
                    "Декларация по НДС как налогового агента. "
                    "Подаётся только электронно через оператора ЭДО. "
                    "Срок — до 25 числа после отчётного квартала."
                ),
                "amount": Decimal("0"),
                "due_date": _next_quarter_25(),
                "status": "pending",
                "recurrence": "quarterly",
                "reminder_days": 14,
                "notes": "Электронная подпись и договор с ЭДО необходимы",
            },
        ]

        for ob in obligations:
            oid = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO public.obligations
                   (id, company_id, obligation_type, title, description,
                    amount, due_date, status, recurrence, reminder_days, notes,
                    created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now(), now())""",
                oid,
                ob["company_id"],
                ob["obligation_type"],
                ob["title"],
                ob["description"],
                ob["amount"],
                ob["due_date"],
                ob["status"],
                ob["recurrence"],
                ob["reminder_days"],
                ob["notes"],
            )
            print(f"  ✅ {ob['title'][:60]}... | {ob['amount']:>10,.0f}₽ | до {ob['due_date']}")

        # Verify
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM public.obligations WHERE company_id = $1", cid
        )
        print(f"\n📊 Всего обязательств для ИП Шульгина: {count}")

    await pool.close()
    print("\n✅ Seed complete!")


def _next_quarter_25() -> date:
    """Next quarter's 25th as date object."""
    today = date.today()
    q = ((today.month - 1) // 3) + 1
    m = q * 3
    y = today.year
    if m < today.month:
        m += 3
        if m > 12:
            m = 3
            y += 1
    return date(y, m, 25)


if __name__ == "__main__":
    asyncio.run(main())
