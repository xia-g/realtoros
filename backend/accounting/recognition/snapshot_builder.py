"""Recognition — builds immutable snapshots of input data for the Rule Engine.

Only reads from accounting_event + external sources at snapshot time.
Never reads live data during decision time.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import asyncpg

from backend.accounting.db.pool import get_pool


async def build_snapshot(event_id: str) -> dict:
    """Build a recognition_snapshot for an event.

    Collects all input data needed by the Rule Engine at decision time,
    frozen in an immutable JSONB blob.

    Returns the snapshot dict with id, version, inputs_json.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Load event
        event = await conn.fetchrow(
            """SELECT id, company_id, event_type, event_date, amount, currency,
                      source_system, source_type, source_id, counterparty_id
               FROM accounting.accounting_event
               WHERE id = $1 AND is_current = true""",
            event_id,
        )
        if not event:
            raise ValueError(f"Event {event_id} not found")

        company_id = event["company_id"]
        event_date = event["event_date"]

        # 2. Collect linked documents (from event_document — snapshot only, not live)
        docs = await conn.fetch(
            """SELECT ed.document_id, ed.role
               FROM accounting.event_document ed
               WHERE ed.event_id = $1""",
            event_id,
        )

        # 3. Collect linked transactions
        txns = await conn.fetch(
            """SELECT et.transaction_id, et.match_type, et.confidence
               FROM accounting.event_transaction et
               WHERE et.event_id = $1""",
            event_id,
        )

        # 4. Get tax regime for the company at event date — frozen into snapshot
        regime = await conn.fetchrow(
            """SELECT id AS regime_id, regime_type, valid_from, valid_to, settings_json
               FROM accounting.tax_regime
               WHERE company_id = $1
                 AND is_active = true
                 AND valid_from <= $2::date
                 AND (valid_to IS NULL OR valid_to >= $2::date)
               ORDER BY valid_from DESC
               LIMIT 1""",
            company_id,
            event_date,
        )

        # 5. Get tax period
        period = await conn.fetchrow(
            """SELECT id AS period_id, period_type, date_from, date_to, status
               FROM accounting.tax_period
               WHERE company_id = $1
                 AND date_from <= $2::date
                 AND date_to >= $2::date
               LIMIT 1""",
            company_id,
            event_date,
        )

        # 6. Helper to convert asyncpg Record to JSON-safe dict
        def _safe_dict(row) -> dict | None:
            if row is None:
                return None
            d = dict(row)
            for k, v in d.items():
                if isinstance(v, UUID):
                    d[k] = str(v)
                elif isinstance(v, (date, datetime)):
                    d[k] = v.isoformat()
            return d

        # 7. Build snapshot
        snapshot_version = await conn.fetchval(
            "SELECT COALESCE(MAX(snapshot_version), 0) + 1 FROM accounting.recognition_snapshot WHERE event_id = $1",
            event_id,
        ) or 1

        inputs = {
            "event": {
                "id": str(event["id"]),
                "event_type": event["event_type"],
                "event_date": event["event_date"].isoformat(),
                "amount": float(event["amount"]),
                "currency": event["currency"],
                "source_system": event["source_system"],
                "source_type": event["source_type"],
                "source_id": event["source_id"],
                "counterparty_id": str(event["counterparty_id"]) if event["counterparty_id"] else None,
            },
            "documents": [
                {"document_id": str(d["document_id"]), "role": d["role"]}
                for d in docs
            ],
            "transactions": [
                {"transaction_id": str(t["transaction_id"]), "match_type": t["match_type"], "confidence": float(t["confidence"])}
                for t in txns
            ],
            "tax_regime": _safe_dict(regime),
            "tax_period": _safe_dict(period),
            "snapshot_metadata": {
                "built_at": datetime.now(timezone.utc).isoformat(),
                "event_version": None,  # filled by caller if available
            },
        }

        snapshot_id = str(uuid4())
        await conn.execute(
            """INSERT INTO accounting.recognition_snapshot (id, event_id, snapshot_version, inputs_json, created_at)
               VALUES ($1, $2, $3, $4::jsonb, now())""",
            snapshot_id,
            event_id,
            snapshot_version,
            json.dumps(inputs),
        )

        return {
            "id": snapshot_id,
            "event_id": event_id,
            "snapshot_version": snapshot_version,
            "inputs_json": inputs,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
