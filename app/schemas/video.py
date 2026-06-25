from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.video import VideoStatus, YoutubePrivacy

class VideoDetectRequest(BaseModel):
    """Schema for file watcher notification request."""
    filename: str = Field(..., description="The name of the video file")
    file_path: str = Field(..., description="The absolute path to the video file")
    file_size_bytes: int = Field(..., description="The size of the video file in bytes")
    channel_name: str = Field(..., description="The name of the channel / directory")

class VideoResponse(BaseModel):
    """Schema for returning detailed video model information."""
    id: int
    channel_id: int
    filename: str
    file_path: str
    file_size_bytes: int
    duration_seconds: Optional[int] = None
    resolution: Optional[str] = None
    screenshot_path: Optional[str] = None
    status: VideoStatus
    youtube_video_id: Optional[str] = None
    youtube_privacy: YoutubePrivacy
    scheduled_time: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None
    retry_count: int
    last_error: Optional[str] = None
    current_title: Optional[str] = None
    current_description: Optional[str] = None
    current_tags: Optional[List[str]] = None
    is_favorite: bool
    notes: Optional[str] = None
    playlist_id: Optional[str] = None
    default_language: Optional[str] = None
    age_restricted: bool = False
    ai_generated: bool = False
    category_id: str = "10"
    made_for_kids: bool = False
    ai_review_note: Optional[str] = None
    metadata_template_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoMetadataUpdate(BaseModel):
    """Schema for updating video metadata draft."""
    title: str = Field(..., max_length=100, description="The video title draft")
    description: str = Field(..., description="The video description draft")
    tags: List[str] = Field(..., description="The list of tags")
    playlist_id: Optional[str] = None
    default_language: Optional[str] = None
    age_restricted: Optional[bool] = None
    ai_generated: Optional[bool] = None
    category_id: Optional[str] = None
    made_for_kids: Optional[bool] = None

class VideoThumbnailSelect(BaseModel):
    """Schema for selecting a thumbnail option."""
    thumbnail_id: int = Field(..., description="The ID of the chosen thumbnail draft")

class ThumbnailDraftResponse(BaseModel):
    """Schema for returning thumbnail draft choices."""
    id: int
    video_id: int
    image_path: str
    style_name: str
    prompt_used: str
    confidence_score: Optional[float] = None
    is_selected: bool

    class Config:
        from_attributes = True


class AIEnhancementResponse(BaseModel):
    """Response containing AI-enhanced titles, description, and tags."""
    titles: List[str]
    description: str
    tags: List[str]


class VideoMoveRequest(BaseModel):
    """Schema for moving a video up or down in the scheduling queue."""
    direction: str = Field(..., description="The direction to move the video: 'up' or 'down'")


