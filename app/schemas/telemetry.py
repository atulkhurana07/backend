from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime, timezone
import uuid


class LocationPayload(BaseModel):
    lat: float
    lng: float
    accuracy_m: Optional[float] = None

    @field_validator("lat")
    @classmethod
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {v}")
        return v

    @field_validator("lng")
    @classmethod
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {v}")
        return v

    @field_validator("accuracy_m")
    @classmethod
    def validate_accuracy(cls, v):
        if v is not None and v < 0:
            raise ValueError("GPS accuracy cannot be negative")
        return v


class MotionPayload(BaseModel):
    speed_kph: Optional[float] = None
    heading_deg: Optional[float] = None

    @field_validator("speed_kph")
    @classmethod
    def validate_speed(cls, v):
        if v is not None and v < 0:
            raise ValueError("Speed cannot be negative")
        return v

    @field_validator("heading_deg")
    @classmethod
    def validate_heading(cls, v):
        if v is not None and not 0 <= v <= 360:
            raise ValueError(f"Heading must be between 0 and 360, got {v}")
        return v


class EnergyPayload(BaseModel):
    soc_pct: Optional[float] = None
    estimated_range_km: Optional[float] = None
    charging: Optional[bool] = None

    @field_validator("soc_pct")
    @classmethod
    def validate_soc(cls, v):
        if v is not None and not 0 <= v <= 100:
            raise ValueError(f"SoC must be between 0 and 100, got {v}")
        return v

    @field_validator("estimated_range_km")
    @classmethod
    def validate_range(cls, v):
        if v is not None and v < 0:
            raise ValueError("Estimated range cannot be negative")
        return v


class DiagnosticsPayload(BaseModel):
    dtcs: Optional[list[str]] = None
    battery_temp_c: Optional[float] = None


class ConnectivityPayload(BaseModel):
    network: Optional[str] = None
    firmware: Optional[str] = None


class TelemetryIngestPayload(BaseModel):
    device_id: str
    vehicle_id: str
    event_id: str
    observed_at: datetime
    location: LocationPayload
    motion: Optional[MotionPayload] = None
    energy: Optional[EnergyPayload] = None
    diagnostics: Optional[DiagnosticsPayload] = None
    connectivity: Optional[ConnectivityPayload] = None
    seq: Optional[int] = None


class TelemetryIngestResponse(BaseModel):
    status: str
    event_id: str
    flags: Optional[dict] = None
    message: Optional[str] = None
