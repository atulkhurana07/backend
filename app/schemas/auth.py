from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserMeResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    department_id: Optional[uuid.UUID] = None
    department_name: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}
