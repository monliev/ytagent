from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field

class VideoAnalyticsItem(BaseModel):
    video_id: int = Field(..., description="Internal database video ID")
    youtube_video_id: str = Field(..., description="YouTube Video ID")
    title: Optional[str] = Field(None, description="Current title of the video")
    views: int = Field(0, description="Total views")
    likes: int = Field(0, description="Total likes")
    comments: int = Field(0, description="Total comments")
    shares: int = Field(0, description="Total shares")
    ctr: Optional[Decimal] = Field(None, description="Click-through rate (CTR)")
    avd_seconds: Optional[int] = Field(None, description="Average view duration in seconds")
    avd_percentage: Optional[Decimal] = Field(None, description="Average view duration percentage")
    recorded_at: Optional[datetime] = Field(None, description="Timestamp of the statistics update")

class VideoAnalyticsResponse(BaseModel):
    videos: List[VideoAnalyticsItem] = Field(default_factory=list)

class PerformanceInsightItem(BaseModel):
    id: int = Field(..., description="Insight unique ID")
    video_id: Optional[int] = Field(None, description="Associated video ID if applicable")
    video_title: Optional[str] = Field(None, description="Title of the associated video")
    insight_type: str = Field(..., description="Type of insight (e.g., anomaly, suggestion, trend)")
    title: str = Field(..., description="Insight heading title")
    message: str = Field(..., description="Detail description of the insight")
    severity: str = Field("info", description="Severity level (info, warning, critical)")
    metric_type: Optional[str] = Field(None, description="Metric analyzed (e.g., ctr, views)")
    metric_value: Optional[Decimal] = Field(None, description="The actual value of the metric")
    metric_average: Optional[Decimal] = Field(None, description="Average or benchmark value")
    suggested_action: Optional[str] = Field(None, description="Suggested action to take")
    is_read: bool = Field(False, description="Whether the user has read the insight")
    created_at: datetime = Field(..., description="Creation timestamp")

class PerformanceInsightResponse(BaseModel):
    insights: List[PerformanceInsightItem] = Field(default_factory=list)
