import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    role: str = Field(default="compute_user")


class UserLogin(BaseModel):
    email: str
    password: str


class UserPermissions(BaseModel):
    can_submit_jobs: bool
    can_manage_nodes: bool
    can_approve_nodes: bool
    can_view_audit: bool
    is_admin: bool


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    role: str
    status: str
    created_at: datetime
    portal_url: str | None = None
    permissions: UserPermissions | None = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse | None = None


class TokenData(BaseModel):
    user_id: str | None = None
    role: str | None = None
