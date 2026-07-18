from uuid import UUID

from backend.core.exceptions import NotFoundError
from backend.core.logging import get_logger
from backend.models import User
from backend.repositories.user import UserRepository

logger = get_logger("app")


class UserService:
    def __init__(self, session):
        self.session = session
        self.repo = UserRepository(session)

    async def authenticate_telegram_user(self, telegram_id: str) -> User:
        user = await self.repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise NotFoundError(message="User not found or deactivated")
        if user.deleted_at is not None:
            raise NotFoundError(message="Account is deactivated")
        logger.info(
            "telegram_auth_success",
            user_id=str(user.id),
            telegram_id=telegram_id,
            role=user.role.name if user.role else "none",
        )
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.repo.get(user_id)

    async def list(self) -> tuple[list[User], int]:
        return await self.repo.list(page=1, page_size=100)
