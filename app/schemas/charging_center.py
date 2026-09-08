from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
from app.models.charging_center import ChargingCenterStatus


class ChargingCenterCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    status: ChargingCenterStatus = ChargingCenterStatus.OPERATIONAL
    description: Optional[str] = None
    amenities: Optional[dict] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    connectors: Optional[dict] = None
    power_kw: Optional[float] = None
    source: Optional[str] = None
    public_visible: bool = True


class ChargingCenterUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    status: Optional[ChargingCenterStatus] = None
    description: Optional[str] = None
    amenities: Optional[dict] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    connectors: Optional[dict] = None
    power_kw: Optional[float] = None
    source: Optional[str] = None
    public_visible: Optional[bool] = None


class ChargingCenterResponse(BaseModel):
    id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    status: ChargingCenterStatus
    description: Optional[str] = None
    amenities: Optional[dict] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    connectors: Optional[dict] = None
    power_kw: Optional[float] = None
    source: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    public_visible: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChargingCenterPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    status: ChargingCenterStatus
    description: Optional[str] = None
    amenities: Optional[dict] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    pincode: Optional[str] = None
    connectors: Optional[dict] = None
    power_kw: Optional[float] = None
    last_verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class ChargingCenterDetailResponse(ChargingCenterPublicResponse):
    pass

