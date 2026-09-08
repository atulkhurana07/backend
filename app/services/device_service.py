from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid

from app.models.device import Device
from app.schemas.device import DeviceCreate


async def create_device(db: AsyncSession, data: DeviceCreate) -> Device:
    device = Device(
        device_code=data.device_code,
        vehicle_id=data.vehicle_id,
        firmware_version=data.firmware_version,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


async def get_devices(
    db: AsyncSession, limit: int = 50, offset: int = 0
) -> tuple[list[Device], int]:
    count_result = await db.execute(select(func.count()).select_from(Device))
    total = count_result.scalar()
    result = await db.execute(
        select(Device).order_by(Device.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total
