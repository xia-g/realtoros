from backend.repositories.base import GenericRepository
from backend.models import Client


class ClientRepository(GenericRepository[Client]):
    """Repository for Client entity."""
    def __init__(self, session):
        super().__init__(session, Client)
