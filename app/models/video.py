import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, String, Integer, Enum, Boolean, Text, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class VideoStatus(str, enum.Enum):
    """Lifecycle status values for a Video."""
    DETECTED = "detected"
    PREPARING = "preparing"
    STAGING = "staging"
    APPROVED = "approved"
    QUEUED = "queued"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"
    DISCARDED = "discarded"
    ERROR = "error"

class YoutubePrivacy(str, enum.Enum):
    """YouTube privacy options."""
    PRIVATE = "private"
    PUBLIC = "public"
    UNLISTED = "unlisted"

class Video(Base):
    """Video database model tracking ingestion and upload states."""
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)

    # File info
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Screenshot
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Lifecycle status
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus), default=VideoStatus.DETECTED, nullable=False, index=True
    )

    # YouTube
    youtube_video_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    youtube_privacy: Mapped[YoutubePrivacy] = mapped_column(
        Enum(YoutubePrivacy), default=YoutubePrivacy.PRIVATE, nullable=False
    )

    # Scheduling & Upload timestamps
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Final/approved metadata (denormalized for quick access)
    current_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)

    # Flags & notes
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel")

    def __repr__(self) -> str:
        return f"<Video id={self.id} filename={self.filename} status={self.status}>"
