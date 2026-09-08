import uuid
from datetime import datetime
from sqlalchemy import String, Float, Boolean, Integer, ForeignKey, DateTime, JSON, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin


class TelemetryEvent(UUIDMixin, Base):
    """Immutable historical telemetry record. Never update or delete."""
    __tablename__ = "telemetry_events"

    event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Location
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Motion
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading_deg: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Energy
    soc_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_range_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    charging: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Diagnostics
    dtcs: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    battery_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Connectivity
    network: Mapped[str | None] = mapped_column(String(20), nullable=True)
    firmware: Mapped[str | None] = mapped_column(String(50), nullable=True)

    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flags: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)  # Validation flags
    raw_payload: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="telemetry_events")

    __table_args__ = (
        UniqueConstraint("device_id", "event_id", name="uq_device_event"),
        Index("ix_telemetry_events_vehicle_observed", "vehicle_id", "observed_at"),
        Index("ix_telemetry_events_received", "received_at"),
    )


class TelemetryLatest(UUIDMixin, Base):
    """Mutable current-state cache. Updated on every new telemetry event."""
    __tablename__ = "telemetry_latest"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), unique=True, nullable=False
    )
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    soc_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_range_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    charging: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dtcs: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    battery_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    network: Mapped[str | None] = mapped_column(String(20), nullable=True)
    firmware: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connectivity_status: Mapped[str] = mapped_column(String(20), default="online", nullable=False)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="telemetry_latest")
