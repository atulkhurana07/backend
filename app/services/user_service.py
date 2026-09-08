from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid

from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.core.security import hash_password


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole(data.role),
        department_id=data.department_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_users(
    db: AsyncSession,
    department_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[User], int]:
    query = select(User)
    count_query = select(func.count()).select_from(User)
    if department_id is not None:
        query = query.where(User.department_id == department_id)
        count_query = count_query.where(User.department_id == department_id)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    result = await db.execute(query.order_by(User.created_at.desc()).limit(limit).offset(offset))
    return list(result.scalars().all()), total


async def update_user_status(
    db: AsyncSession, user_id: uuid.UUID, is_active: bool
) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user
