from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    """Schema for login request."""
    username: str = Field(..., description="Username or Telegram User ID")
    password: str = Field(..., description="Password")

class TokenResponse(BaseModel):
    """Schema for returning an access token."""
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    """Schema for returning user information."""
    id: int
    telegram_id: int
    username: Optional[str] = None
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
