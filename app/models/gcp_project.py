import enum
from datetime import datetime, date
from sqlalchemy import BigInteger, ForeignKey, String, Integer, Date, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class GCPProjectStatus(str, enum.Enum):
    """Status values for a GCP Project."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    QUOTA_EXCEEDED = "quota_exceeded"

class GCPProject(Base):
    """GCPProject database model for tracking channel API quotas."""
    __tablename__ = "gcp_projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    project_name: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    client_secret_path: Mapped[str] = mapped_column(String(256), nullable=False)
    
    quota_limit: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    quota_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reset: Mapped[date] = mapped_column(Date, default=func.current_date(), nullable=False, index=True)
    
    status: Mapped[GCPProjectStatus] = mapped_column(Enum(GCPProjectStatus), default=GCPProjectStatus.ACTIVE, nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel")

    def __repr__(self) -> str:
        return f"<GCPProject id={self.id} project_id={self.project_id} status={self.status}>"
