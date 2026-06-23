from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field

class GCPProjectBase(BaseModel):
    project_name: str = Field(..., description="Human readable project name")
    project_id: str = Field(..., description="GCP Project ID")
    quota_limit: int = Field(default=10000, description="Daily API unit quota limit")
    status: str = Field(default="active", description="Project status (active, suspended, quota_exceeded)")

class GCPProjectCreate(GCPProjectBase):
    client_secret_json: str = Field(..., description="Raw Google Client Secret JSON string")

class GCPProjectResponse(GCPProjectBase):
    id: int
    channel_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChannelCredentialsCreate(BaseModel):
    gcp_project_id: str = Field(..., description="GCP Project ID to associate with")
    refresh_token: str = Field(..., description="OAuth2 Refresh Token")

class ChannelCredentialsResponse(BaseModel):
    id: int
    channel_id: int
    gcp_project_id: str
    is_active: bool
    last_refreshed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
