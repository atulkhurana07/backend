import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.charging_center import ChargingCenter
from app.models.charging_center_operator import ChargingCenterOperator
from app.schemas.charging_center import ChargingCenterResponse, ChargingCenterUpdate

async def get_operator_stations(db: AsyncSession, user_id: uuid.UUID) -> list[ChargingCenterResponse]:
    query = select(ChargingCenter).join(ChargingCenterOperator, ChargingCenter.id == ChargingCenterOperator.charging_center_id).where(
        ChargingCenterOperator.user_id == user_id,
        ChargingCenterOperator.is_active == True
    )
    res = await db.execute(query)
    return [ChargingCenterResponse.model_validate(c) for c in res.scalars().all()]

async def get_operator_station_by_id(db: AsyncSession, station_id: uuid.UUID, user_id: uuid.UUID, is_admin: bool = False) -> ChargingCenterResponse:
    c = await db.get(ChargingCenter, station_id)
    if not c:
        raise HTTPException(status_code=404, detail="Charging center not found")
        
    if not is_admin:
        op_query = select(ChargingCenterOperator).where(
            ChargingCenterOperator.charging_center_id == station_id,
            ChargingCenterOperator.user_id == user_id,
            ChargingCenterOperator.is_active == True
        )
        op = (await db.execute(op_query)).scalar_one_or_none()
        if not op:
            raise HTTPException(status_code=403, detail="Not authorized for this charging center")
            
    return ChargingCenterResponse.model_validate(c)

async def update_operator_station(db: AsyncSession, station_id: uuid.UUID, data: ChargingCenterUpdate, user_id: uuid.UUID, is_admin: bool = False) -> ChargingCenterResponse:
    c = await db.get(ChargingCenter, station_id)
    if not c:
        raise HTTPException(status_code=404, detail="Charging center not found")
        
    if not is_admin:
        op_query = select(ChargingCenterOperator).where(
            ChargingCenterOperator.charging_center_id == station_id,
            ChargingCenterOperator.user_id == user_id,
            ChargingCenterOperator.is_active == True
        )
        op = (await db.execute(op_query)).scalar_one_or_none()
        if not op:
            raise HTTPException(status_code=403, detail="Not authorized for this charging center")

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(c, k, v)
        
    await db.commit()
    await db.refresh(c)
    return ChargingCenterResponse.model_validate(c)
