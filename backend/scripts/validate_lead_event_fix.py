"""Validation script for lead_event model fix.

Verifies:
1. Model imports without error
2. No circular imports in models package
3. FK ondelete policies match migration
4. created_at has server_default
"""

import sys
import os

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_import():
    from backend.models.lead_event import LeadEvent
    print("PASS: lead_event imports OK")
    return LeadEvent


def test_all_models():
    from backend.models import LeadEvent
    print("PASS: models package imports OK (no circular imports)")
    return LeadEvent


def test_lead_event_fks(LeadEvent):
    columns = [
        ("lead_id", "CASCADE"),
        ("from_user_id", "SET NULL"),
        ("to_user_id", "SET NULL"),
        ("changed_by", "SET NULL"),
    ]
    all_ok = True
    for col_name, expected_policy in columns:
        col = getattr(LeadEvent, col_name).property.columns[0]
        fks = list(col.foreign_keys)
        assert len(fks) == 1, f"{col_name}: expected 1 FK, got {len(fks)}"
        fk = fks[0]
        ondelete = fk.ondelete
        if ondelete == expected_policy:
            print(f"PASS: {col_name} ondelete={ondelete}")
        else:
            print(f"FAIL: {col_name} ondelete={ondelete}, expected={expected_policy}")
            all_ok = False
    return all_ok


def test_created_at_server_default(LeadEvent):
    col = LeadEvent.created_at.property.columns[0]
    sd = col.server_default
    if sd is not None:
        print(f"PASS: created_at has server_default: {sd.arg}")
        return True
    else:
        print("FAIL: created_at has no server_default")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDATION: lead_event.py fixes")
    print("=" * 60)
    print()

    LeadEvent = test_import()
    print()

    test_all_models()
    print()

    print("--- FK ondelete policies ---")
    fk_ok = test_lead_event_fks(LeadEvent)
    print()

    print("--- created_at server_default ---")
    sd_ok = test_created_at_server_default(LeadEvent)
    print()

    print("=" * 60)
    if fk_ok and sd_ok:
        print("RESULT: ALL CHECKS PASSED ✅")
    else:
        print("RESULT: SOME CHECKS FAILED ❌")
    print("=" * 60)
