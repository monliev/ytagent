import enum
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import BigInteger, ForeignKey, String, Text, Enum, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class LogLevel(str, enum.Enum):
    """Logging severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class SystemLog(Base):
    """SystemLog database model for structured logging and auditing."""
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Context relations
    video_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    # Content
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Context trace
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)

    # Relationships
    video: Mapped[Optional["Video"]] = relationship("Video")
    channel: Mapped[Optional["Channel"]] = relationship("Channel")
    user: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<SystemLog id={self.id} level={self.level} service={self.service} event={self.event_type}>"
