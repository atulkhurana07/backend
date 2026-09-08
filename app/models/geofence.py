import uuid
from datetime import datetime
from sqlalchemy import String, Float, Boolean, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin
import enum


class GeofenceType(str, enum.Enum):
    DEPOT = "depot"
    STATION = "station"
    HOSPITAL = "hospital"
    BOUNDARY = "boundary"
    RESTRICTED = "restricted"


class Geofence(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "geofences"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    geofence_type: Mapped[GeofenceType] = mapped_column(
        SAEnum(GeofenceType, name="geofence_type"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True
    )
    boundary: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)  # GeoJSON polygon
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_m: Mapped[float | None] = mapped_column(Float, nullable=True)  # For circular geofences
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    department = relationship("Department", back_populates="geofences")
