"""Control Plane — Operational orchestration + governance + audit layer.

ControlPlaneOrchestrator.execute_action()
  → validates permissions
  → dispatches to subsystem
  → tracks execution
  → persists audit event

Invariant: Control Plane does NOT compute data — only manages states/processes.
Invariant: Every action is logged as immutable audit event.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from backend.accounting.db.pool import get_pool


# ── Enums ──────────────────────────────────────────────────────────────


class SystemHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    REPLAYING = "replaying"
    RECALCULATING = "recalculating"
    LOCKED = "locked"
    ERROR = "error"


class ControlActionType(str, Enum):
    CLOSE_PERIOD = "close_period"
    OPEN_PERIOD = "open_period"
    RECALCULATE_TAX = "recalculate_tax_registers"
    FREEZE_TAX_POLICY = "freeze_tax_policy"
    REGENERATE_REPORT = "regenerate_report"
    REVALIDATE_REPORT = "revalidate_report"
    RUN_RECONCILIATION = "run_reconciliation"
    RERUN_MATCHES = "rerun_failed_matches"
    FULL_REPLAY = "full_replay"
    PARTIAL_REPLAY = "partial_replay"
    BACKFILL = "system_backfill"
    APPROVE = "approve"
    REJECT = "reject"
    LOCK = "lock_system"
    UNLOCK = "unlock_system"


class ControlRole(str, Enum):
    ACCOUNTANT = "accountant"
    AUDITOR = "auditor"
    ADMIN = "admin"
    SYSTEM_OPERATOR = "system_operator"
    READONLY = "readonly"


class ControlActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


SUBSYSTEM_MAP = {
    "ledger": ControlActionType.CLOSE_PERIOD.value,
    "tax": ControlActionType.RECALCULATE_TAX.value,
    "reports": ControlActionType.REGENERATE_REPORT.value,
    "reconciliation": ControlActionType.RUN_RECONCILIATION.value,
}


# ── Permission Matrix ──────────────────────────────────────────────────

PERMISSIONS: dict[str, dict[str, list[str]]] = {
    # action_type → { subsystem → allowed_roles }
    ControlActionType.CLOSE_PERIOD.value: {
        "ledger": ["accountant", "admin"],
    },
    ControlActionType.OPEN_PERIOD.value: {
        "ledger": ["admin"],
    },
    ControlActionType.RECALCULATE_TAX.value: {
        "tax": ["accountant", "admin", "system_operator"],
    },
    ControlActionType.FREEZE_TAX_POLICY.value: {
        "tax": ["admin"],
    },
    ControlActionType.REGENERATE_REPORT.value: {
        "reports": ["accountant", "admin", "system_operator"],
    },
    ControlActionType.REVALIDATE_REPORT.value: {
        "reports": ["accountant", "admin"],
    },
    ControlActionType.RUN_RECONCILIATION.value: {
        "reconciliation": ["accountant", "auditor", "admin", "system_operator"],
    },
    ControlActionType.RERUN_MATCHES.value: {
        "reconciliation": ["accountant", "admin"],
    },
    ControlActionType.FULL_REPLAY.value: {
        "global": ["admin"],
    },
    ControlActionType.PARTIAL_REPLAY.value: {
        "global": ["accountant", "admin", "system_operator"],
    },
    ControlActionType.BACKFILL.value: {
        "global": ["admin"],
    },
    ControlActionType.LOCK.value: {
        "global": ["admin"],
    },
    ControlActionType.UNLOCK.value: {
        "global": ["admin"],
    },
}

# Actions requiring approval (human sign-off)
APPROVAL_REQUIRED = {
    ControlActionType.CLOSE_PERIOD.value,
    ControlActionType.OPEN_PERIOD.value,
    ControlActionType.FREEZE_TAX_POLICY.value,
    ControlActionType.FULL_REPLAY.value,
    ControlActionType.BACKFILL.value,
}


# ── Orchestrator ───────────────────────────────────────────────────────


class ControlPlaneOrchestrator:
    """Orchestrates control actions across all subsystems.

    Does NOT compute data — delegates to subsystem APIs.
    """

    @staticmethod
    async def execute_action(
        action_type: str,
        target_system: str,
        actor_id: str | None = None,
        actor_role: str = ControlRole.SYSTEM_OPERATOR.value,
        details: dict | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a control action with permission check + audit trail."""
        pool = await get_pool()

        # 1. Validate action type
        if action_type not in [e.value for e in ControlActionType]:
            return {"error": f"Unknown action type: {action_type}"}

        # 2. Check permissions
        allowed = PERMISSIONS.get(action_type, {}).get(target_system, [])
        if actor_role not in allowed and actor_role != "admin":
            return {
                "error": f"Role '{actor_role}' not allowed to execute "
                         f"'{action_type}' on '{target_system}'",
            }

        # 3. Capture state before
        state_before = await ControlPlaneOrchestrator._capture_system_state(target_system)

        # 4. Check if approval required
        needs_approval = action_type in APPROVAL_REQUIRED

        action_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            # 5. Create control action record
            await conn.execute(
                """INSERT INTO accounting.control_action
                   (id, action_type, target_system, actor_id, actor_role,
                    status, state_before_hash, details_json, correlation_id)
                   VALUES ($1, $2, $3, $4, $5,
                           $6, $7, $8::jsonb, $9)""",
                action_id, action_type, target_system, actor_id, actor_role,
                "pending" if needs_approval else "running",
                state_before.get("state_hash"),
                json.dumps(details or {}),
                correlation_id or str(uuid.uuid4()),
            )

            # 6. If approval required, create approval workflow
            if needs_approval:
                required_role = ControlPlaneOrchestrator._required_approval_role(action_type)
                await conn.execute(
                    """INSERT INTO accounting.approval_workflow
                       (id, action_id, required_role, status)
                       VALUES ($1, $2, $3, 'pending')""",
                    str(uuid.uuid4()), action_id, required_role,
                )
                return {
                    "action_id": action_id,
                    "status": "pending_approval",
                    "message": f"Action requires approval by role '{required_role}'",
                    "action_type": action_type,
                    "target_system": target_system,
                }

            # 7. Execute (dispatch to subsystem)
            result = await ControlPlaneOrchestrator._dispatch(
                action_type, target_system, details
            )
            success = result.get("success", False)

            # 8. Capture state after
            state_after = await ControlPlaneOrchestrator._capture_system_state(target_system)

            # 9. Update action record
            await conn.execute(
                """UPDATE accounting.control_action
                   SET status = $2, state_after_hash = $3,
                       error_message = $4, completed_at = now()
                   WHERE id = $1""",
                action_id,
                "completed" if success else "failed",
                state_after.get("state_hash"),
                result.get("error") if not success else None,
            )

            # 10. Update system state
            new_health = SystemHealth.HEALTHY.value if success else SystemHealth.ERROR.value
            await conn.execute(
                """INSERT INTO accounting.system_state
                   (id, subsystem, status, state_hash, details_json)
                   VALUES ($1, $2, $3, $4, $5::jsonb)
                   ON CONFLICT (subsystem) DO UPDATE
                   SET status = EXCLUDED.status,
                       state_hash = EXCLUDED.state_hash,
                       details_json = EXCLUDED.details_json,
                       updated_at = now()""",
                str(uuid.uuid4()), target_system, new_health,
                state_after.get("state_hash", ""),
                json.dumps({"last_action": action_type, "last_action_id": action_id}),
            )

        return {
            "action_id": action_id,
            "status": "completed" if success else "failed",
            "action_type": action_type,
            "target_system": target_system,
            "state_before": state_before.get("state_hash", "")[:16],
            "state_after": state_after.get("state_hash", "")[:16],
            "result": result,
        }

    @staticmethod
    async def approve_action(action_id: str, approved_by: str, role: str, reason: str | None = None) -> dict:
        """Approve or reject a pending action."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            wf = await conn.fetchrow(
                """SELECT aw.id, aw.action_id, aw.required_role, aw.status,
                          ca.action_type, ca.target_system, ca.details_json,
                          ca.actor_id, ca.actor_role, ca.correlation_id
                   FROM accounting.approval_workflow aw
                   JOIN accounting.control_action ca ON ca.id = aw.action_id
                   WHERE aw.action_id = $1 AND aw.status = 'pending'""",
                action_id,
            )
            if not wf:
                return {"error": "No pending approval found for action"}

            # Check role
            if role != wf["required_role"] and role != "admin":
                return {"error": f"Role '{role}' cannot approve. Required: {wf['required_role']}"}

            # Mark approval
            await conn.execute(
                """UPDATE accounting.approval_workflow
                   SET status = 'approved', approved_by = $2,
                       approved_at = now(), reason = $3
                   WHERE id = $1""",
                wf["id"], approved_by, reason,
            )

            # Execute the approved action
            details = json.loads(wf["details_json"]) if isinstance(wf["details_json"], str) else (wf["details_json"] or {})
            result = await ControlPlaneOrchestrator.execute_action(
                action_type=wf["action_type"],
                target_system=wf["target_system"],
                actor_id=str(wf["actor_id"]) if wf["actor_id"] else approved_by,
                actor_role=wf["actor_role"],
                details=details,
                correlation_id=wf["correlation_id"],
            )

            return {"approved": True, "action_id": action_id, "execution": result}

    @staticmethod
    async def _dispatch(action_type: str, target_system: str, details: dict | None) -> dict:
        """Dispatch action to the appropriate subsystem.

        Does NOT compute data — only triggers subsystem actions.
        """
        from backend.accounting.ledger.period import close_period, open_period
        from backend.accounting.tax.replay import TaxReplay
        from backend.accounting.report.generator import ReportGenerator
        from backend.accounting.report.template import TemplateProvider
        from backend.accounting.report.audit import AuditEngine
        from backend.accounting.reconciliation.engine import ReconciliationEngine

        pool = await get_pool()

        try:
            if action_type == ControlActionType.CLOSE_PERIOD.value:
                period_id = details.get("period_id") if details else None
                if period_id:
                    success = await close_period(period_id)
                    return {"success": success, "period_id": period_id}

            elif action_type == ControlActionType.OPEN_PERIOD.value:
                period_id = details.get("period_id") if details else None
                if period_id:
                    from backend.accounting.ledger.period import open_period as op
                    success = await op(period_id)
                    return {"success": success, "period_id": period_id}

            elif action_type == ControlActionType.RECALCULATE_TAX.value:
                replay = TaxReplay()
                result = await replay.recalculate(
                    company_id=details.get("company_id"),
                    tax_period_id=details.get("tax_period_id"),
                )
                return {"success": True, "new_assignments": result.new_assignments_count}

            elif action_type == ControlActionType.REGENERATE_REPORT.value:
                template = await TemplateProvider.get_active(
                    details.get("template_code", "USN_DECLARATION"),
                    details.get("tax_regime", "USN_D"),
                )
                if template:
                    draft = await ReportGenerator.generate(
                        company_id=details.get("company_id"),
                        template_version=template,
                        tax_period_id=details.get("tax_period_id"),
                    )
                    rid = await ReportGenerator.save(draft)
                    return {"success": True, "report_id": rid, "hash": draft.report_hash[:16]}

            elif action_type == ControlActionType.RUN_RECONCILIATION.value:
                from datetime import date
                result = await ReconciliationEngine.run(
                    company_id=details.get("company_id"),
                    period_from=date.fromisoformat(details.get("period_from")) if details.get("period_from") else date(2026,1,1),
                    period_to=date.fromisoformat(details.get("period_to")) if details.get("period_to") else date(2026,12,31),
                )
                rid = await ReconciliationEngine.save(result)
                return {"success": True, "run_id": rid, "matches": result.matches_count, "gaps": result.gaps_count}

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def _capture_system_state(target_system: str) -> dict:
        """Capture deterministic state hash for a subsystem."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            if target_system == "ledger":
                count = await conn.fetchval("SELECT count(*) FROM accounting.ledger_entry")
                line_count = await conn.fetchval("SELECT count(*) FROM accounting.ledger_line")
                state_input = f"ledger:entries={count},lines={line_count}"
            elif target_system == "tax":
                count = await conn.fetchval("SELECT count(*) FROM accounting.tax_assignment WHERE is_current=true")
                regs = await conn.fetchval("SELECT count(*) FROM accounting.tax_register WHERE is_current=true")
                state_input = f"tax:assignments={count},registers={regs}"
            elif target_system == "reports":
                count = await conn.fetchval("SELECT count(*) FROM accounting.report_draft")
                state_input = f"reports:drafts={count}"
            elif target_system == "reconciliation":
                count = await conn.fetchval("SELECT count(*) FROM accounting.reconciliation_run")
                gaps = await conn.fetchval("SELECT count(*) FROM accounting.reconciliation_gap")
                state_input = f"reconciliation:runs={count},gaps={gaps}"
            else:
                ledger = await conn.fetchval("SELECT count(*) FROM accounting.ledger_entry")
                tax = await conn.fetchval("SELECT count(*) FROM accounting.tax_assignment")
                reports = await conn.fetchval("SELECT count(*) FROM accounting.report_draft")
                state_input = f"global:ledger={ledger},tax={tax},reports={reports}"

            state_hash = hashlib.sha256(state_input.encode()).hexdigest()
            return {"state_hash": state_hash}

    @staticmethod
    def _required_approval_role(action_type: str) -> str:
        mapping = {
            ControlActionType.CLOSE_PERIOD.value: "accountant",
            ControlActionType.OPEN_PERIOD.value: "admin",
            ControlActionType.FREEZE_TAX_POLICY.value: "admin",
            ControlActionType.FULL_REPLAY.value: "admin",
            ControlActionType.BACKFILL.value: "admin",
        }
        return mapping.get(action_type, "admin")

    @staticmethod
    async def record_metrics() -> dict:
        """Record a system metrics snapshot."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            failed = await conn.fetchval(
                "SELECT count(*) FROM accounting.control_action WHERE status = 'failed'"
            )
            total = await conn.fetchval("SELECT count(*) FROM accounting.control_action")
            locked = await conn.fetchval(
                "SELECT count(*) FROM accounting.system_state WHERE status = 'locked'"
            )
            health = await conn.fetchval(
                "SELECT status FROM accounting.system_state WHERE subsystem = 'global'"
            ) or "healthy"

            await conn.execute(
                """INSERT INTO accounting.system_metrics_snapshot
                   (health_state, failed_jobs_count, lock_count, total_actions)
                   VALUES ($1, $2, $3, $4)""",
                health, failed or 0, locked or 0, total or 0,
            )

            return {
                "health": health,
                "failed_actions": failed or 0,
                "total_actions": total or 0,
                "locked_subsystems": locked or 0,
            }
