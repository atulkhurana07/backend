import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, JSON, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin
import enum


class AlertType(str, enum.Enum):
    LOW_SOC = "LOW_SOC"
    LOW_RANGE = "LOW_RANGE"
    VEHICLE_OFFLINE = "VEHICLE_OFFLINE"
    GEOFENCE_BREACH = "GEOFENCE_BREACH"
    OVERSPEED = "OVERSPEED"
    HIGH_BATTERY_TEMP = "HIGH_BATTERY_TEMP"
    DIAGNOSTIC_FAULT = "DIAGNOSTIC_FAULT"
    CHARGING_INTERRUPTED = "CHARGING_INTERRUPTED"


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class Alert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "alerts"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False, index=True
    )
    alert_type: Mapped[AlertType] = mapped_column(SAEnum(AlertType, name="alert_type"), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(SAEnum(AlertSeverity, name="alert_severity"), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, name="alert_status"), default=AlertStatus.ACTIVE, nullable=False, index=True
    )
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON().with_variant(JSONB, "postgresql"), nullable=True)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="alerts")
    acknowledged_by_user = relationship("User", foreign_keys=[acknowledged_by])
