from fastmcp import FastMCP

from tools.project_tools import (
    get_vision,
    get_architecture,
    get_entities,
    get_roadmap,
    get_project_status,
    get_development_rules,
    get_all_skills,
    project_context,
    search_project_docs,
    domain_context as _domain_context,
    create_task as _create_task,
    list_tasks as _list_tasks,
    update_task as _update_task,
    update_project_status as _update_project_status,
)

from tools.deal_tools import (
    check_deal_completeness as _check_deal_completeness,
    validate_document_package as _validate_document_package,
    get_regulation as _get_regulation,
    check_deal_status as _check_deal_status,
    check_deal_risks as _check_deal_risks,
    get_regulation_updates as _get_regulation_updates,
    get_next_actions as _get_next_actions,
)

mcp = FastMCP(
    name="RealEstateOS"
)


@mcp.tool
def search_project(query: str):
    return search_project_docs(query)

@mcp.tool
def project_vision():
    return get_vision()


@mcp.tool
def project_architecture():
    return get_architecture()


@mcp.tool
def project_entities():
    return get_entities()


@mcp.tool
def project_roadmap():
    return get_roadmap()


@mcp.tool
def project_status():
    return get_project_status()


@mcp.tool
def development_rules():
    return get_development_rules()


@mcp.tool
def all_skills():
    return get_all_skills()


@mcp.tool
def project_context():
    return project_context()


@mcp.tool
def domain_context(domain: str):
    """Load domain-specific documentation bundle.

    Args:
        domain: Domain name (e.g. 'accounting', 'crm', 'deal', 'knowledge', 'auth')
    """
    return _domain_context(domain)


# ─── Backlog tools ────────────────────────────────────────


@mcp.tool
def create_task(title: str, description: str = "", category: str = "general", priority: str = "medium"):
    """Create a new task in the technical backlog."""
    return _create_task(title, description, category, priority)


@mcp.tool
def list_tasks(status: str = "", category: str = ""):
    """List backlog tasks, optionally filtered by status or category."""
    return _list_tasks(status, category)


@mcp.tool
def update_task(task_id: str, status: str = ""):
    """Update a task's status (pending / in_progress / completed / cancelled)."""
    return _update_task(task_id, status)


# ─── Project status tools ─────────────────────────────────


@mcp.tool
def update_project_status(item: str, to_section: str):
    """Move an item from ## Pending to ## <to_section> → Completed."""
    return _update_project_status(item, to_section)


# ─── Deal Governance tools (P5.5) ─────────────────────────


@mcp.tool
def check_deal_completeness(deal_id: str, deal_type: str = "SALE_APARTMENT", completed_checkpoints: list[str] | None = None, uploaded_documents: list[str] | None = None):
    """Check a deal's compliance completeness and return a score (0-100)."""
    return _check_deal_completeness(deal_id, deal_type, completed_checkpoints, uploaded_documents)


@mcp.tool
def validate_document_package(deal_type: str, uploaded_documents: list[str]):
    """Validate which required documents are missing for a deal type."""
    return _validate_document_package(deal_type, uploaded_documents)


@mcp.tool
def get_regulation(query: str, min_trust: str = "COMMUNITY", limit: int = 5):
    """Search regulations by query, filtered by minimum trust level."""
    return _get_regulation(query, min_trust, limit)


# ─── Deal Copilot tools (Sprint 5) ────────────────────────


@mcp.tool
def check_deal_status(deal_id: str, deal_type: str = "SALE_APARTMENT"):
    """Check overall deal status including compliance score and risk assessment."""
    return _check_deal_status(deal_id, deal_type)


@mcp.tool
def check_deal_risks(deal_id: str):
    """Assess deal risks: ownership, minor owners, mortgage, restrictions."""
    return _check_deal_risks(deal_id)


@mcp.tool
def get_regulation_updates(source: str = "", since_days: int = 7):
    """Get recent regulation updates from Росреестр, ФНС, Минфин, etc."""
    return _get_regulation_updates(source, since_days)


@mcp.tool
def get_next_actions(deal_id: str, deal_type: str = "SALE_APARTMENT"):
    """Get recommended next actions for a deal based on compliance gaps and risks."""
    return _get_next_actions(deal_id, deal_type)


if __name__ == "__main__":
    mcp.run()
