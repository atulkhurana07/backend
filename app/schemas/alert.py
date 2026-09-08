from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class AlertResponse(BaseModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    alert_type: str
    severity: str
    status: str
    first_seen: datetime
    last_seen: datetime
    acknowledged_by: Optional[uuid.UUID] = None
    acknowledged_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertAckRequest(BaseModel):
    resolution_note: Optional[str] = None
