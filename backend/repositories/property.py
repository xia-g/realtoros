from backend.repositories.base import GenericRepository
from backend.models import Property


class PropertyRepository(GenericRepository[Property]):
    def __init__(self, session):
        super().__init__(session, Property)
