"""Knowledge Message — a single turn in a knowledge session.

SECURITY: Always accessed through session ownership check.
Never query messages directly without session.user_id validation.
"""

# Re-export from knowledge_session module to keep model layout flat
from backend.models.knowledge_session import KnowledgeMessage  # noqa: F401
