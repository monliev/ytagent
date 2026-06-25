from datetime import datetime, time
from typing import Optional, Any
from sqlalchemy import BigInteger, Time, Boolean, String, Text, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

class Channel(Base):
    """Channel database model."""
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    genre: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    folder_path: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    preferred_time: Mapped[time] = mapped_column(Time, default=time(10, 0, 0), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    made_for_kids: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    playlist_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    default_language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    age_restricted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category_id: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Presets
    preset_title_template: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    preset_description_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preset_tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    preset_social_links: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    preset_templates: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    title_pool: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Thumbnail preset
    thumbnail_style_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    thumbnail_style_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_style_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Active GCP project reference
    gcp_project_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Channel id={self.id} name={self.name} genre={self.genre}>"
