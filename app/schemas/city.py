from pydantic import BaseModel
from typing import Optional
import uuid

class CityResponse(BaseModel):
    id: uuid.UUID
    name: str
    state: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = {"from_attributes": True}

class StateResponse(BaseModel):
    state: str
    city_count: int

    model_config = {"from_attributes": True}
