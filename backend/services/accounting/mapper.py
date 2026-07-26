"""Stream 1 — Document → Accounting entry mapper."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from backend.services.accounting.models import AccountingEntry, EntryLine


# Mapping rules: list of (label, account_code, debit_field, credit_field)
# Where debit_field/credit_field = key from document profile.fields
INVOICE_RULES = [
    ("Expense", "26", "amount", None),         # Debit expense
    ("Supplier", "60", None, "amount"),         # Credit supplier
    ("Input VAT", "19", "vat", None),           # Debit VAT
]

ACT_RULES = [
    ("Expense", "26", "amount", None),
    ("Supplier", "60", None, "amount"),
]

BANK_STATEMENT_RULES = [
    ("Cash", "51", "amount", None),
    ("Counterparty", "76", None, "amount"),
]

MAPPINGS = {
    "invoice": (INVOICE_RULES, None),
    "act": (ACT_RULES, None),
    "bank_statement": (BANK_STATEMENT_RULES, None),
}


class AccountingMapper:
    """Transform document extraction results into accounting entries."""

    def map_to_entry(self, document_id: str, doc_type: str,
                     fields: dict, period_id: str,
                     journal_id: str = "journal-general",
                     entry_date: date | None = None) -> AccountingEntry | None:
        """Create an AccountingEntry from document fields.

        Args:
            document_id: From Document Layer.
            doc_type: From classification (invoice, act, etc.).
            fields: Extracted fields dict (supplier, amount, vat, date, etc.).
            period_id: Accounting period.
            journal_id: Target journal.
            entry_date: Entry date (defaults to extracted date or today).

        Returns:
            AccountingEntry in DRAFT status, or None if no mapping found.
        """
        rules = MAPPINGS.get(doc_type)
        if rules is None:
            return None

        rule_list, _extra = rules
        lines: list[EntryLine] = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for label, account_code, debit_field, credit_field in rule_list:
            if debit_field:
                raw = fields.get(debit_field, "0")
                try:
                    amount = Decimal(str(raw).replace(",", ".").replace(" ", ""))
                except Exception:
                    amount = Decimal("0")
                # If we also have a VAT field and this is a debit line
                # (expense), subtract VAT to avoid booking the VAT portion twice
                vat_raw = fields.get("vat", "0")
                try:
                    vat_amount = Decimal(str(vat_raw).replace(",", ".").replace(" ", ""))
                except Exception:
                    vat_amount = Decimal("0")
                if vat_amount > 0 and debit_field == "amount":
                    # Expense = amount - vat (VAT is booked separately)
                    amount = amount - vat_amount
                    if amount < 0:
                        amount = Decimal("0")
                if amount > 0:
                    lines.append(EntryLine(
                        line_id=str(uuid.uuid4()),
                        account_id=account_code,
                        debit=amount,
                        credit=Decimal("0"),
                        description=label,
                    ))
                    total_debit += amount

            if credit_field:
                raw = fields.get(credit_field, "0")
                try:
                    amount = Decimal(str(raw).replace(",", ".").replace(" ", ""))
                except Exception:
                    amount = Decimal("0")
                if amount > 0:
                    lines.append(EntryLine(
                        line_id=str(uuid.uuid4()),
                        account_id=account_code,
                        debit=Decimal("0"),
                        credit=amount,
                        description=label,
                    ))
                    total_credit += amount

        if not lines:
            return None

        # Determine entry date
        edate = entry_date
        if edate is None:
            raw_date = fields.get("date", "")
            if raw_date:
                try:
                    parts = raw_date.replace("/", "-").split("-")
                    if len(parts) == 3:
                        edate = date(int(parts[0]), int(parts[1]), int(parts[2]))
                except Exception:
                    edate = date.today()
            else:
                edate = date.today()

        description = f"Auto: {doc_type} {fields.get('invoice_number', fields.get('contract_number', ''))}"

        return AccountingEntry(
            entry_id=str(uuid.uuid4()),
            journal_id=journal_id,
            document_id=document_id,
            period_id=period_id,
            entry_date=edate,
            description=description.strip(),
            status="DRAFT",
            lines=lines,
            created_at=datetime.now(),
        )
