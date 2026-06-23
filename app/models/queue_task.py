import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Enum, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class QueueTaskStatus(str, enum.Enum):
    """Execution status values for a Queue Task."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class QueueTask(Base):
    """QueueTask database model representing the upload task queue."""
    __tablename__ = "queue_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), unique=True, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)

    # Priority & Scheduling
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Status
    status: Mapped[QueueTaskStatus] = mapped_column(
        Enum(QueueTaskStatus), default=QueueTaskStatus.PENDING, nullable=False, index=True
    )

    # Execution tracking
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Celery integration
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video")
    channel: Mapped["Channel"] = relationship("Channel")

    def __repr__(self) -> str:
        return f"<QueueTask id={self.id} video_id={self.video_id} status={self.status}>"
