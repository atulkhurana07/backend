from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class DeviceCreate(BaseModel):
    device_code: str
    vehicle_id: uuid.UUID
    firmware_version: Optional[str] = None


class DeviceResponse(BaseModel):
    id: uuid.UUID
    device_code: str
    vehicle_id: uuid.UUID
    firmware_version: Optional[str] = None
    status: str
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
