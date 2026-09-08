from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.charging_center import ChargingCenterResponse, ChargingCenterUpdate
from app.services.charging_operator_service import get_operator_stations, get_operator_station_by_id, update_operator_station

router = APIRouter(prefix="/api/charging-operator", tags=["charging-operator"])

@router.get("/stations", response_model=List[ChargingCenterResponse])
async def api_get_operator_stations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.CHARGING_CENTER_OPERATOR))
):
    if current_user.role == UserRole.PLATFORM_ADMIN:
        from app.services.public_data_service import get_public_charging_centers
        return await get_public_charging_centers(db)
    return await get_operator_stations(db, current_user.id)

@router.get("/stations/{id}", response_model=ChargingCenterResponse)
async def api_get_operator_station_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.CHARGING_CENTER_OPERATOR))
):
    is_admin = current_user.role == UserRole.PLATFORM_ADMIN
    return await get_operator_station_by_id(db, id, current_user.id, is_admin)

@router.patch("/stations/{id}", response_model=ChargingCenterResponse)
async def api_update_operator_station(
    id: uuid.UUID,
    data: ChargingCenterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PLATFORM_ADMIN, UserRole.CHARGING_CENTER_OPERATOR))
):
    is_admin = current_user.role == UserRole.PLATFORM_ADMIN
    return await update_operator_station(db, id, data, current_user.id, is_admin)
