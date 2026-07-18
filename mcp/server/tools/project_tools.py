import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..memory import read_doc
from ..memory import search_docs

ROOT = Path(__file__).resolve().parents[3]
BACKLOG_PATH = ROOT / "docs" / "backlog.json"
STATUS_PATH = ROOT / "docs" / "project_status.md"


def _load_backlog() -> list[dict]:
    if not BACKLOG_PATH.exists():
        return []
    try:
        return json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_backlog(tasks: list[dict]) -> None:
    BACKLOG_PATH.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── Backlog: create / list / update ───────────────────────────────


def create_task(
    title: str,
    description: str = "",
    category: str = "general",
    priority: str = "medium",
) -> str:
    tasks = _load_backlog()
    now = datetime.now(timezone.utc).isoformat()
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "status": "pending",
        "category": category,
        "priority": priority,
        "created_at": now,
        "updated_at": now,
    }
    tasks.append(task)
    _save_backlog(tasks)
    return json.dumps(task, ensure_ascii=False, indent=2)


def list_tasks(status: str = "", category: str = "") -> str:
    tasks = _load_backlog()
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if category:
        tasks = [t for t in tasks if t["category"] == category]
    if not tasks:
        return "[]"
    return json.dumps(tasks, ensure_ascii=False, indent=2)


def update_task(task_id: str, status: str = "") -> str:
    tasks = _load_backlog()
    for t in tasks:
        if t["id"] == task_id:
            if status:
                t["status"] = status
            t["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_backlog(tasks)
            return json.dumps(t, ensure_ascii=False, indent=2)
    return json.dumps({"error": f"Task {task_id} not found"})


# ─── Project status: move items from Pending → Completed ───────────


def update_project_status(item: str, to_section: str) -> str:
    """Move an item from ## Pending to ## <to_section> → Completed.

    Args:
        item: The exact item name (e.g. 'ER Model')
        to_section: Target section header (e.g. 'Documentation', 'Infrastructure')
    """
    if not STATUS_PATH.exists():
        return json.dumps({"error": "project_status.md not found"})

    text = STATUS_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # ── 1. Find and remove item from Pending section ──
    in_pending = False
    pending_found = False
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Pending"):
            in_pending = True
            new_lines.append(line)
            continue
        if in_pending and stripped.startswith("## "):
            # Reached next section — Pending section ended
            in_pending = False
            new_lines.append(line)
            continue
        if in_pending and stripped == f"- {item}":
            pending_found = True
            continue  # skip — remove from Pending
        new_lines.append(line)

    if not pending_found:
        return json.dumps({"error": f"'{item}' not found in ## Pending"})

    # ── 2. Find target section and insert item under Completed ──
    target_header = f"## {to_section}"
    in_target = False
    after_completed = False
    result_lines: list[str] = []
    inserted = False

    for line in new_lines:
        stripped = line.strip()
        if stripped.startswith(target_header):
            in_target = True
            after_completed = False
            result_lines.append(line)
            continue
        if in_target and stripped.startswith("## "):
            # Reached next section — insert before if not yet done
            if not inserted:
                result_lines.append(f"- {item}\n")
                inserted = True
            in_target = False
            after_completed = False
            result_lines.append(line)
            continue
        if in_target and stripped == "Completed:":
            after_completed = True
            result_lines.append(line)
            continue
        if in_target and after_completed:
            if stripped.startswith("- ") and stripped[2:].strip().lower() > item.lower():
                # Insert in alphabetical order
                if not inserted:
                    result_lines.append(f"- {item}\n")
                    inserted = True
                result_lines.append(line)
                continue
            elif stripped.startswith("- "):
                result_lines.append(line)
                continue
            else:
                # End of Completed list — insert if not yet done
                if not inserted:
                    result_lines.append(f"- {item}\n")
                    inserted = True
                result_lines.append(line)
                continue
        result_lines.append(line)

    # If target section never appeared
    if not inserted:
        return json.dumps({"error": f"Section '## {to_section}' not found"})

    STATUS_PATH.write_text("".join(result_lines), encoding="utf-8")
    return json.dumps(
        {"success": True, "item": item, "moved_to": f"{to_section} → Completed"},
        ensure_ascii=False,
        indent=2,
    )


# ─── Existing read helpers ─────────────────────────────────────────


def search_project_docs(query: str):
    return search_docs(query)


def get_vision():
    return read_doc("vision/project_vision.md")


def get_architecture():
    return read_doc("architecture/system_architecture.md")


def get_entities():
    return read_doc("domain/entities.md")


def get_roadmap():
    return read_doc("roadmap/mvp.md")


def domain_context(domain: str) -> str:
    """Load domain-specific documentation bundle.

    Args:
        domain: One of 'accounting', 'crm', 'deal', 'knowledge', 'auth'

    Returns:
        JSON dict of all relevant docs for the domain.
    """
    import json
    from ..memory import read_doc
    from ..memory import DOCS_DIR

    DOMAIN_MAP = {
        "accounting": [
            "accounting/architecture.md",
            "accounting/freeze.md",
            "accounting/roadmap.md",
            "accounting/ledger_boundary.md",
            "accounting/posting_model.md",
            "accounting/phase3_freeze.md",
            "accounting/phase3_acceptance.md",
            "accounting/tax_boundary.md",
            "accounting/tax_assignment_model.md",
            "accounting/tax_register_model.md",
            "accounting/phase4_freeze.md",
            "accounting/phase4_acceptance.md",
            "accounting/chart_of_accounts.md",
            "accounting/reporting_boundary.md",
            "accounting/report_ai_boundary.md",
            "accounting/phase4_consolidated_report.md",
            "accounting/RC1-declaration.md",
            "accounting/integration/bank_import.md",
            "accounting/integration/document_intake.md",
            "accounting/integration/ocr.md",
            "accounting/integration/final_report.md",
            "accounting/validation/environment.md",
            "accounting/validation/smoke.md",
            "accounting/validation/e2e.md",
            "accounting/validation/failure.md",
            "accounting/validation/explainability.md",
            "accounting/validation/performance.md",
            "accounting/validation/final_report.md",
            "accounting/backlog/reconciliation_perf.md",
            "adr/ADR-013-ledger-boundary.md",
            "adr/ADR-014-tax-assignment-layer.md",
            "adr/ADR-015-report-is-generated-artifact.md",
        ],
    }

    files = DOMAIN_MAP.get(domain, [])
    if not files:
        return json.dumps({"error": f"Unknown domain: {domain}"})

    # Add testing docs if they exist
    testing_dir = DOCS_DIR / domain / "testing"
    if testing_dir.exists():
        for f in sorted(testing_dir.glob("*.md")):
            rel = str(f.relative_to(DOCS_DIR))
            if rel not in files:
                files.append(rel)

    # Auto-scan integration/, validation/, backlog/, runbooks/ subdirs
    for sub in ["integration", "validation", "backlog", "runbooks"]:
        sub_dir = DOCS_DIR / domain / sub
        if sub_dir.exists():
            for f in sorted(sub_dir.glob("*.md")):
                rel = str(f.relative_to(DOCS_DIR))
                if rel not in files:
                    files.append(rel)

    result = {}
    for f in files:
        content = read_doc(f)
        if not content.startswith("Document not found"):
            result[f] = content
    if not result:
        return json.dumps({"error": f"No docs found for domain: {domain}"})
    return json.dumps(result, ensure_ascii=False, indent=2)


def get_project_status():
    return read_doc("project_status.md")


def get_development_rules():
    return read_doc("development_rules.md")


def get_all_skills():
    ROOT = Path(__file__).resolve().parents[3]
    skills_dir = ROOT / "docs" / "skills"
    result = {}
    if skills_dir.exists():
        for f in sorted(skills_dir.glob("*.md")):
            result[f.stem] = f.read_text(encoding="utf-8", errors="ignore")
    return json.dumps(result, ensure_ascii=False)


def project_context():
    ctx = {
        "vision": get_vision(),
        "architecture": get_architecture(),
        "entities": get_entities(),
        "roadmap": get_roadmap(),
        "status": get_project_status(),
        "rules": get_development_rules(),
        "skills": get_all_skills(),
    }
    return json.dumps(ctx, ensure_ascii=False)
