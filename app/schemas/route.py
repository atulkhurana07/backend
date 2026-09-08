from pydantic import BaseModel
from typing import Optional, List
import uuid

class RouteResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: Optional[str] = None
    city: str
    state: str
    description: Optional[str] = None
    geometry: Optional[dict] = None
    color: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}

class StopResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: Optional[str] = None
    latitude: float
    longitude: float
    city: str
    state: str

    model_config = {"from_attributes": True}

class StopDetailResponse(StopResponse):
    serving_routes: List[RouteResponse] = []
    
    model_config = {"from_attributes": True}

class RouteDetailResponse(RouteResponse):
    stops: List[StopResponse] = []
    geometry: Optional[dict] = None

    model_config = {"from_attributes": True}
