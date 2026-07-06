from sqlalchemy import select

from backend.repositories.base import GenericRepository
from backend.models import User


class UserRepository(GenericRepository[User]):
    def __init__(self, session):
        super().__init__(session, User)

    async def get_by_telegram_id(self, telegram_id: str) -> User | None:
        stmt = select(User).where(
            User.telegram_id == str(telegram_id),
            User.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
