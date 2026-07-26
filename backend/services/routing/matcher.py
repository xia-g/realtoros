"""Stream 3 — Entity matching for routing context."""
from __future__ import annotations


class EntityMatcher:
    """Match extracted fields to existing business entities.

    Product Layer — queries existing business tables.
    No Platform changes.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(self._dsn)

    def match_counterparty(self, name: str, inn: str = "") -> str | None:
        """Find counterparty by name or INN. Returns counterparty_id or None."""
        if not name and not inn:
            return None
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if inn:
                    cur.execute(
                        "SELECT id FROM counterparties WHERE inn = %s LIMIT 1",
                        (inn,),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["id"])

                if name:
                    cur.execute(
                        "SELECT id FROM counterparties WHERE name ILIKE %s OR short_name ILIKE %s LIMIT 1",
                        (f"%{name}%", f"%{name}%"),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["id"])
        finally:
            conn.close()
        return None

    def match_deal(self, contract_number: str, counterparty_id: str = "") -> str | None:
        """Find deal by contract number. Returns deal_id or None."""
        if not contract_number:
            return None
        import psycopg2
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                if counterparty_id:
                    cur.execute(
                        "SELECT id FROM deals WHERE contract_number = %s AND client_id = %s LIMIT 1",
                        (contract_number, counterparty_id),
                    )
                else:
                    cur.execute(
                        "SELECT id FROM deals WHERE contract_number = %s LIMIT 1",
                        (contract_number,),
                    )
                row = cur.fetchone()
                return str(row[0]) if row else None
        finally:
            conn.close()

    def match_period(self, date_str: str) -> str | None:
        """Find accounting period containing the given date. Returns period_id or None."""
        if not date_str:
            return None
        import psycopg2
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM accounting_periods WHERE %s::date BETWEEN start_date AND end_date LIMIT 1",
                    (date_str,),
                )
                row = cur.fetchone()
                return str(row[0]) if row else None
        finally:
            conn.close()

    def resolve(self, fields: dict, doc_type: str) -> dict:
        """Resolve all entities from extracted fields.

        Returns dict of matched entity IDs.
        """
        matched = {}

        # Counterparty
        supplier = fields.get("supplier", "")
        if supplier:
            counterparty_id = self.match_counterparty(supplier)
            if counterparty_id:
                matched["counterparty_id"] = counterparty_id

        customer = fields.get("customer", "")
        if customer and "counterparty_id" not in matched:
            counterparty_id = self.match_counterparty(customer)
            if counterparty_id:
                matched["counterparty_id"] = counterparty_id

        # Deal
        contract_no = fields.get("contract_number", "")
        if contract_no:
            deal_id = self.match_deal(contract_no, matched.get("counterparty_id", ""))
            if deal_id:
                matched["deal_id"] = deal_id

        # Accounting period
        date = fields.get("date", "")
        if date:
            period_id = self.match_period(date)
            if period_id:
                matched["accounting_period_id"] = period_id

        return matched
