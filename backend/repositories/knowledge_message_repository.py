"""Knowledge Message Repository — re-export from session repo.

All message operations are accessed through session context.
"""
# Re-export to keep repository layout consistent
from backend.repositories.knowledge_session_repository import KnowledgeMessageRepository  # noqa: F401
