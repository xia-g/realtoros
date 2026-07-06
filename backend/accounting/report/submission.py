"""Submission Package — transport artifact for report submission.

Submission does not own the report.
Stores only transport metadata: submission_id, report_version, hashes, external status.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.accounting.db.pool import get_pool


@dataclass
class SubmissionPackage:
    submission_id: str
    report_id: str
    report_version: int
    transport_payload_hash: str
    payload_format: str
    external_receipt: str | None
    external_status: str | None


class SubmissionService:
    """Manages submission packages (transport artifacts)."""

    @staticmethod
    async def create(
        report_id: str,
        payload_format: str = "xml",
    ) -> SubmissionPackage:
        """Create a submission package for a report.

        Does NOT copy register/assignment data — only references.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            report = await conn.fetchrow(
                "SELECT id, report_version, report_hash FROM accounting.report_draft WHERE id = $1",
                report_id,
            )
            if not report:
                raise ValueError(f"Report {report_id} not found")

            if report["report_version"] is None:
                raise ValueError(f"Report {report_id} has no version")

            # Build transport payload hash
            hash_input = {
                "report_id": str(report["id"]),
                "report_version": report["report_version"],
                "report_hash": report["report_hash"],
                "format": payload_format,
            }
            payload_hash = hashlib.sha256(
                json.dumps(hash_input, sort_keys=True).encode()
            ).hexdigest()

            submission_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO accounting.submission_package
                   (id, report_id, report_version, transport_payload_hash, payload_format, submitted_at)
                   VALUES ($1, $2, $3, $4, $5, now())""",
                submission_id,
                report["id"],
                report["report_version"],
                payload_hash,
                payload_format,
            )

            # Update report status
            await conn.execute(
                "UPDATE accounting.report_draft SET status = 'submitted', updated_at = now() WHERE id = $1",
                report_id,
            )

            return SubmissionPackage(
                submission_id=submission_id,
                report_id=str(report["id"]),
                report_version=report["report_version"],
                transport_payload_hash=payload_hash,
                payload_format=payload_format,
                external_receipt=None,
                external_status=None,
            )

    @staticmethod
    async def update_status(submission_id: str, external_status: str, receipt: str | None = None) -> bool:
        """Update external submission status from FNS."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE accounting.submission_package "
                "SET external_status = $2, external_receipt = COALESCE($3, external_receipt) "
                "WHERE id = $1",
                submission_id, external_status, receipt,
            )
            return "UPDATE 1" in str(result)

    @staticmethod
    async def get_by_report(report_id: str) -> list[SubmissionPackage]:
        """Get all submissions for a report."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM accounting.submission_package WHERE report_id = $1 ORDER BY submitted_at DESC",
                report_id,
            )
            return [
                SubmissionPackage(
                    submission_id=str(r["id"]),
                    report_id=str(r["report_id"]),
                    report_version=r["report_version"],
                    transport_payload_hash=r["transport_payload_hash"],
                    payload_format=r["payload_format"],
                    external_receipt=r["external_receipt"],
                    external_status=r["external_status"],
                )
                for r in rows
            ]
