from datetime import datetime, time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ChannelBase(BaseModel):
    name: str = Field(..., description="Channel name")
    genre: str = Field(..., description="Genre of content (e.g. lofi, tech, cooking)")
    folder_path: str = Field(..., description="NAS watch directory path")
    preferred_time: time = Field(default=time(10, 0, 0), description="Preferred daily upload time")
    is_active: bool = Field(default=True)
    auto_approve: bool = Field(default=False)
    made_for_kids: bool = Field(default=False)
    preset_title_template: Optional[str] = None
    preset_description_template: Optional[str] = None
    preset_tags: Optional[List[str]] = None
    preset_social_links: Optional[Dict[str, Any]] = None
    preset_templates: Optional[List[Dict[str, Any]]] = None
    thumbnail_style_name: Optional[str] = None
    thumbnail_style_prompt: Optional[str] = None
    gcp_project_id: Optional[str] = None
    playlist_id: Optional[str] = None
    default_language: Optional[str] = None
    age_restricted: bool = Field(default=False)
    ai_generated: bool = Field(default=False)
    category_id: Optional[str] = None

class ChannelCreate(ChannelBase):
    pass

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    genre: Optional[str] = None
    folder_path: Optional[str] = None
    preferred_time: Optional[time] = None
    is_active: Optional[bool] = None
    auto_approve: Optional[bool] = None
    made_for_kids: Optional[bool] = None
    preset_title_template: Optional[str] = None
    preset_description_template: Optional[str] = None
    preset_tags: Optional[List[str]] = None
    preset_social_links: Optional[Dict[str, Any]] = None
    preset_templates: Optional[List[Dict[str, Any]]] = None
    thumbnail_style_name: Optional[str] = None
    thumbnail_style_prompt: Optional[str] = None
    gcp_project_id: Optional[str] = None
    playlist_id: Optional[str] = None
    default_language: Optional[str] = None
    age_restricted: Optional[bool] = None
    ai_generated: Optional[bool] = None
    category_id: Optional[str] = None

class ChannelResponse(ChannelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
