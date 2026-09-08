from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class VehicleCreate(BaseModel):
    vehicle_code: str
    registration_number: Optional[str] = None
    vehicle_type: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    department_id: uuid.UUID
    public_visible: bool = True


class VehicleUpdate(BaseModel):
    registration_number: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    is_active: Optional[bool] = None
    public_visible: Optional[bool] = None


class VehicleResponse(BaseModel):
    id: uuid.UUID
    vehicle_code: str
    registration_number: Optional[str] = None
    vehicle_type: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    department_id: uuid.UUID
    is_active: bool
    public_visible: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VehicleWithTelemetryResponse(BaseModel):
    id: uuid.UUID
    vehicle_code: str
    vehicle_type: str
    department_id: uuid.UUID
    is_active: bool
    # Latest telemetry
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kph: Optional[float] = None
    heading_deg: Optional[float] = None
    soc_pct: Optional[float] = None
    estimated_range_km: Optional[float] = None
    charging: Optional[bool] = None
    connectivity_status: Optional[str] = None
    last_seen: Optional[datetime] = None
    # Real hardware diagnostic fields
    battery_temp_c: Optional[float] = None
    dtcs: Optional[list[str]] = None

    model_config = {"from_attributes": True}


class VehiclePublicResponse(BaseModel):
    """Sanitized vehicle data for public consumption."""
    id: uuid.UUID
    vehicle_code: Optional[str] = None
    vehicle_type: str
    department_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kph: Optional[float] = None
    heading_deg: Optional[float] = None
    direction: Optional[str] = None  # N/S/E/W
    soc_pct: Optional[float] = None
    charging: Optional[bool] = None
    status: Optional[str] = None  # online/offline
    route_id: Optional[uuid.UUID] = None
    route_name: Optional[str] = None
    route_code: Optional[str] = None
    route_color: Optional[str] = None
    next_stop_name: Optional[str] = None
    eta_next_stop_mins: Optional[int] = None
    origin_stop: Optional[str] = None
    destination_stop: Optional[str] = None
    schedule_status: Optional[str] = None
    last_updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
