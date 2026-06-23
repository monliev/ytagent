from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, String, Text, Numeric, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class ThumbnailDraft(Base):
    """ThumbnailDraft database model representing AI-generated options."""
    __tablename__ = "thumbnail_drafts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)

    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    style_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_used: Mapped[str] = mapped_column(Text, nullable=False)

    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    selection_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video")

    def __repr__(self) -> str:
        return f"<ThumbnailDraft id={self.id} video_id={self.video_id} is_selected={self.is_selected}>"
