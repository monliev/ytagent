import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, String, Text, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class NotificationType(str, enum.Enum):
    """Types of notifications sent to users."""
    VIDEO_READY = "video_ready"
    UPLOAD_COMPLETE = "upload_complete"
    UPLOAD_FAILED = "upload_failed"
    DAILY_REPORT = "daily_report"
    ANOMALY_ALERT = "anomaly_alert"
    COPYRIGHT_ALERT = "copyright_alert"
    QUOTA_WARNING = "quota_warning"
    SYSTEM_ALERT = "system_alert"

class NotificationChannel(str, enum.Enum):
    """Notification channels."""
    TELEGRAM = "telegram"
    DASHBOARD = "dashboard"

class NotificationStatus(str, enum.Enum):
    """Status values for notification delivery."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class NotificationHistory(Base):
    """NotificationHistory database model tracking delivered alerts/approvals."""
    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    notification_type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel), default=NotificationChannel.TELEGRAM, nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), default=NotificationStatus.SENT, nullable=False, index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Context relations
    video_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=True)

    # Timestamps
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    video: Mapped[Optional["Video"]] = relationship("Video")
    yt_channel: Mapped[Optional["Channel"]] = relationship("Channel")

    def __repr__(self) -> str:
        return f"<NotificationHistory id={self.id} type={self.notification_type} status={self.status}>"
