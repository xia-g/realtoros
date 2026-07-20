def __getattr__(name):
    if name == "MemoryKnowledgeRevisionRepository":
        from infrastructure.knowledge_persistence.memory_knowledge_revision_repository import (
            MemoryKnowledgeRevisionRepository,
        )
        return MemoryKnowledgeRevisionRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["MemoryKnowledgeRevisionRepository"]
