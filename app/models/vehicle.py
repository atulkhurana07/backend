import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin
import enum


class VehicleType(str, enum.Enum):
    ELECTRIC_BUS = "electric_bus"
    FIRE_EV = "fire_ev"
    UTILITY_EV = "utility_ev"
    AMBULANCE_EV = "ambulance_ev"
    OTHER = "other"


class Vehicle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"

    vehicle_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(SAEnum(VehicleType, name="vehicle_type"), nullable=False)
    make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    public_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    department = relationship("Department", back_populates="vehicles")
    device = relationship("Device", back_populates="vehicle", uselist=False)
    telemetry_latest = relationship("TelemetryLatest", back_populates="vehicle", uselist=False)
    telemetry_events = relationship("TelemetryEvent", back_populates="vehicle", lazy="dynamic")
    alerts = relationship("Alert", back_populates="vehicle", lazy="dynamic")
    trips = relationship("Trip", back_populates="vehicle", lazy="dynamic")
