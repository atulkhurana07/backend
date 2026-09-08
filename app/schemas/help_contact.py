from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class HelpContactResponse(BaseModel):
    id: uuid.UUID
    city: Optional[str] = None
    state: Optional[str] = None
    department: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    category: str
    availability: Optional[str] = None
    last_verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
