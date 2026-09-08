import uuid
from datetime import datetime
import enum
from sqlalchemy import String, Float, Boolean, DateTime, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin


class ChargingCenterStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    LIMITED = "limited"
    OFFLINE = "offline"
    UNDER_MAINTENANCE = "under_maintenance"


class ChargingCenter(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "charging_centers"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[ChargingCenterStatus] = mapped_column(
        SAEnum(ChargingCenterStatus, name="charging_center_status_enum"),
        default=ChargingCenterStatus.OPERATIONAL,
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    amenities: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    operating_hours: Mapped[str | None] = mapped_column(String(100), nullable=True)

    connectors: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    public_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
