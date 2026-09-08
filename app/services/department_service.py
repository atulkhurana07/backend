from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid

from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate


async def create_department(db: AsyncSession, data: DepartmentCreate) -> Department:
    dept = Department(name=data.name, code=data.code, description=data.description)
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept


async def get_departments(db: AsyncSession, limit: int = 50, offset: int = 0) -> tuple[list[Department], int]:
    count_result = await db.execute(select(func.count()).select_from(Department))
    total = count_result.scalar()
    result = await db.execute(
        select(Department).order_by(Department.name).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def get_department_by_id(db: AsyncSession, dept_id: uuid.UUID) -> Optional[Department]:
    result = await db.execute(select(Department).where(Department.id == dept_id))
    return result.scalar_one_or_none()


async def update_department(db: AsyncSession, dept_id: uuid.UUID, data: DepartmentUpdate) -> Optional[Department]:
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if dept is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    await db.commit()
    await db.refresh(dept)
    return dept
