from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.schemas.user import UserCreate, UserResponse
from backend.services.user import UserService

router = APIRouter()


@router.get("/by-telegram/{telegram_id}", response_model=UserResponse)
async def get_user_by_telegram(telegram_id: str, session: AsyncSession = Depends(get_session)):
    svc = UserService(session)
    try:
        user = await svc.authenticate_telegram_user(telegram_id)
        return user
    except Exception:
        raise HTTPException(status_code=404, detail="User not found or deactivated")


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(body: UserCreate, session: AsyncSession = Depends(get_session)):
    service = UserService(session)
    user = await service.create(**body.model_dump(exclude_unset=True))
    return user


@router.get("", response_model=list[UserResponse])
async def list_users(session: AsyncSession = Depends(get_session)):
    service = UserService(session)
    items, total = await service.list()
    return items


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, session: AsyncSession = Depends(get_session)):
    service = UserService(session)
    user = await service.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
