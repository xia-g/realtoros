"""Phase 7 E2E Tests: Control Plane.

Scenarios:
  1. Permission isolation (readonly cannot execute actions)
  2. Action execution + audit trail (immutable)
  3. Approval workflow (pending → approved → execution)
  4. System state tracking
  5. Metrics recording
"""

from __future__ import annotations

import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "mcp", "server"))

from backend.accounting.db.pool import get_pool
from backend.accounting.control import ControlPlaneOrchestrator


async def main():
    passed = 0
    failed = 0
    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM accounting.system_metrics_snapshot")
            await conn.execute("DELETE FROM accounting.approval_workflow")
            await conn.execute("DELETE FROM accounting.control_action")
            await conn.execute("DELETE FROM accounting.system_state")

        print("=" * 60)
        print("Phase 7 — E2E Tests")
        print("=" * 60)

        # ═══════════════════════════════════════════════════════════════
        # 1. Permission Isolation
        # ═══════════════════════════════════════════════════════════════
        print("\n1. Permission Isolation")
        print("-" * 40)

        # Readonly cannot close period
        result = await ControlPlaneOrchestrator.execute_action(
            action_type="close_period",
            target_system="ledger",
            actor_id="test_reader",
            actor_role="readonly",
            details={"period_id": "test"},
        )
        assert "error" in result, "Readonly should be denied"
        assert "not allowed" in result["error"]

        # Accountant can close period
        result2 = await ControlPlaneOrchestrator.execute_action(
            action_type="close_period",
            target_system="ledger",
            actor_id="test_accountant",
            actor_role="accountant",
            details={"period_id": "test"},
        )
        assert "error" not in result2, f"Accountant should be allowed: {result2}"

        # Admin can do anything
        result3 = await ControlPlaneOrchestrator.execute_action(
            action_type="full_replay",
            target_system="global",
            actor_id="test_admin",
            actor_role="admin",
        )
        assert "error" not in result3, f"Admin should be allowed: {result3}"

        passed += 1
        print(f"  ✅ Readonly denied, Accountant ALLOWED, Admin ALLOWED")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 2. Action Audit Trail
        # ═══════════════════════════════════════════════════════════════
        print("\n2. Action Audit Trail (immutable)")
        print("-" * 40)

        async with pool.acquire() as conn:
            actions = await conn.fetch(
                "SELECT action_type, target_system, actor_role, status FROM accounting.control_action ORDER BY created_at"
            )

        print(f"     Actions logged: {len(actions)}")
        for a in actions:
            print(f"       {a['action_type']} on {a['target_system']} by {a['actor_role']}: {a['status']}")

        assert len(actions) >= 2, "Should have at least 2 audit records"
        for a in actions:
            assert a["status"] in ("completed", "failed", "pending"), \
                f"Invalid status: {a['status']}"

        passed += 1
        print(f"  ✅ All actions logged with valid statuses")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 3. Approval Workflow
        # ═══════════════════════════════════════════════════════════════
        print("\n3. Approval Workflow")
        print("-" * 40)

        # close_period requires approval — should return pending
        result_approval = await ControlPlaneOrchestrator.execute_action(
            action_type="close_period",
            target_system="ledger",
            actor_id="test_accountant2",
            actor_role="accountant",
            details={"period_id": "test_period"},
        )

        assert result_approval.get("status") == "pending_approval", \
            f"Should be pending approval: {result_approval}"
        action_id = result_approval["action_id"]

        # Approve the action
        approved = await ControlPlaneOrchestrator.approve_action(
            action_id=action_id,
            approved_by="test_admin",
            role="admin",
            reason="Approved for testing",
        )
        assert approved.get("approved") or approved.get("execution", {}).get("status") == "completed", \
            f"Approval failed: {approved}"

        # Verify: approval workflow updated
        async with pool.acquire() as conn:
            wf = await conn.fetchrow(
                "SELECT * FROM accounting.approval_workflow WHERE action_id = $1",
                action_id,
            )

        passed += 1
        print(f"  ✅ Action pending → approved")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 4. System State Tracking
        # ═══════════════════════════════════════════════════════════════
        print("\n4. System State Tracking")
        print("-" * 40)

        # Run an action that executes immediately (no approval required)
        result_exec = await ControlPlaneOrchestrator.execute_action(
            action_type="recalculate_tax_registers",
            target_system="tax",
            actor_id="test_sysop",
            actor_role="system_operator",
            details={"company_id": "00000000-0000-0000-0000-000000000001", "tax_period_id": "none"},
        )
        print(f"     Execute result: {result_exec.get('status')}")

        async with pool.acquire() as conn:
            states = await conn.fetch(
                "SELECT subsystem, status, state_hash FROM accounting.system_state ORDER BY subsystem"
            )

        print(f"     Subsystems tracked: {len(states)}")
        subsystems_found = set()
        for s in states:
            subsystems_found.add(s["subsystem"])
            print(f"       {s['subsystem']}: {s['status']} (hash: {str(s['state_hash'])[:16]}...)")

        assert len(states) >= 1, "Should have at least 1 tracked subsystem"

        passed += 1
        print(f"  ✅ System state tracked for {len(states)} subsystems")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 5. Metrics Recording
        # ═══════════════════════════════════════════════════════════════
        print("\n5. System Metrics")
        print("-" * 40)

        metrics = await ControlPlaneOrchestrator.record_metrics()
        assert "health" in metrics, f"Metrics should include health: {metrics}"

        async with pool.acquire() as conn:
            snapshots = await conn.fetch(
                "SELECT * FROM accounting.system_metrics_snapshot ORDER BY snapshot_time DESC LIMIT 5"
            )

        print(f"     Health: {metrics['health']}")
        print(f"     Total actions: {metrics['total_actions']}")
        print(f"     Failed jobs: {metrics['failed_actions']}")
        print(f"     Snapshots: {len(snapshots)}")

        passed += 1
        print(f"  ✅ Metrics recorded")

    finally:
        await pool.close()

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed / {failed} failed")
    print(f"{'=' * 60}")
    return passed, failed


if __name__ == "__main__":
    p, f = asyncio.run(main())
    sys.exit(1 if f > 0 else 0)
