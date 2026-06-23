from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from sqlalchemy import BigInteger, ForeignKey, String, Integer, Numeric, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class AnalyticsRecord(Base):
    """AnalyticsRecord database model tracking performance snapshots over time."""
    __tablename__ = "analytics_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Timing metrics
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    hours_since_publish: Mapped[int] = mapped_column(Integer, nullable=False)

    # Core performance metrics
    views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    views_gained: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Engagement
    likes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    dislikes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Derived metrics
    ctr: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True, index=True)
    avd_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    avd_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Structured metadata
    traffic_sources: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    demographics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    raw_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video")
    channel: Mapped["Channel"] = relationship("Channel")

    def __repr__(self) -> str:
        return f"<AnalyticsRecord id={self.id} video_id={self.video_id} views={self.views} hours={self.hours_since_publish}>"
