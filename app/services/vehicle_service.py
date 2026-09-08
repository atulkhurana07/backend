from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from typing import Optional
import uuid

from app.models.vehicle import Vehicle
from app.models.telemetry import TelemetryLatest
from app.models.department import Department


async def get_vehicles_with_telemetry(
    db: AsyncSession,
    department_id: Optional[uuid.UUID] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list, int]:
    """Get vehicles with their latest telemetry, scoped by department."""
    query = (
        select(Vehicle, TelemetryLatest)
        .outerjoin(TelemetryLatest, Vehicle.id == TelemetryLatest.vehicle_id)
        .where(Vehicle.is_active == True)
    )
    
    if department_id is not None:
        query = query.where(Vehicle.department_id == department_id)
    
    # Count
    count_query = select(func.count()).select_from(Vehicle).where(Vehicle.is_active == True)
    if department_id is not None:
        count_query = count_query.where(Vehicle.department_id == department_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    query = query.order_by(Vehicle.vehicle_code).limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()
    
    return rows, total


async def get_vehicle_by_id(
    db: AsyncSession,
    vehicle_id: uuid.UUID,
    department_id: Optional[uuid.UUID] = None,
):
    """Get single vehicle with telemetry. Enforces department scope."""
    query = (
        select(Vehicle, TelemetryLatest)
        .outerjoin(TelemetryLatest, Vehicle.id == TelemetryLatest.vehicle_id)
        .where(Vehicle.id == vehicle_id)
    )
    if department_id is not None:
        query = query.where(Vehicle.department_id == department_id)
    
    result = await db.execute(query)
    row = result.one_or_none()
    return row


async def get_vehicle_track(
    db: AsyncSession,
    vehicle_id: uuid.UUID,
    department_id: Optional[uuid.UUID] = None,
    limit: int = 100,
):
    """Get recent telemetry events for a vehicle. Enforces department scope."""
    from app.models.telemetry import TelemetryEvent
    
    # First verify vehicle access
    vehicle_query = select(Vehicle).where(Vehicle.id == vehicle_id)
    if department_id is not None:
        vehicle_query = vehicle_query.where(Vehicle.department_id == department_id)
    vehicle_result = await db.execute(vehicle_query)
    vehicle = vehicle_result.scalar_one_or_none()
    if vehicle is None:
        return None
    
    track_query = (
        select(TelemetryEvent)
        .where(TelemetryEvent.vehicle_id == vehicle_id)
        .order_by(TelemetryEvent.observed_at.desc())
        .limit(limit)
    )
    result = await db.execute(track_query)
    return result.scalars().all()
