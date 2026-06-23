from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, Boolean, String, Text, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class ChannelCredentials(Base):
    """ChannelCredentials database model for OAuth isolation."""
    __tablename__ = "channel_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    gcp_project_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # Encrypted credentials
    oauth_credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    oauth_refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    oauth_token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Encryption metadata
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel")

    def __repr__(self) -> str:
        return f"<ChannelCredentials id={self.id} channel_id={self.channel_id} gcp_project_id={self.gcp_project_id}>"
