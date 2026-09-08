from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    action: str
    object_type: str
    object_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None
    metadata: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
