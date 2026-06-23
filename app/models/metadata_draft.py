import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, JSON, Numeric, Boolean, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class MetadataGenerationType(str, enum.Enum):
    """How the metadata draft was generated."""
    AUTO = "auto"
    MANUAL_EDIT = "manual_edit"
    AI_SUGGESTION = "ai_suggestion"

class ABTestGroup(str, enum.Enum):
    """A/B test groups for experimental title/thumbnail variants."""
    CONTROL = "control"
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"

class MetadataDraft(Base):
    """MetadataDraft database model representing AI generated metadata options."""
    __tablename__ = "metadata_drafts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)

    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    generation_type: Mapped[MetadataGenerationType] = mapped_column(
        Enum(MetadataGenerationType), default=MetadataGenerationType.AUTO, nullable=False
    )

    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    tone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    approved_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    supervisor_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ab_test_group: Mapped[ABTestGroup] = mapped_column(Enum(ABTestGroup), default=ABTestGroup.CONTROL, nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video")
    approver: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<MetadataDraft id={self.id} video_id={self.video_id} version={self.version_number} is_approved={self.is_approved}>"
