from backend.repositories.base import GenericRepository
from backend.models import Deal


class DealRepository(GenericRepository[Deal]):
    def __init__(self, session):
        super().__init__(session, Deal)
