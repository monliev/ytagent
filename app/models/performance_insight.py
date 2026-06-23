import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, String, Text, Enum, Numeric, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class InsightType(str, enum.Enum):
    """Types of AI insights."""
    ANOMALY = "anomaly"
    SUGGESTION = "suggestion"
    AB_TEST_RESULT = "ab_test_result"
    TREND = "trend"
    MILESTONE = "milestone"

class InsightSeverity(str, enum.Enum):
    """Insight severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class PerformanceInsight(Base):
    """PerformanceInsight database model representing AI insights and suggestions."""
    __tablename__ = "performance_insights"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)

    # Classification
    insight_type: Mapped[InsightType] = mapped_column(Enum(InsightType), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[InsightSeverity] = mapped_column(
        Enum(InsightSeverity), default=InsightSeverity.INFO, nullable=False, index=True
    )

    # Metrics references
    metric_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    metric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    metric_average: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Actions & Read status
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Telegram notification audit
    sent_to_telegram: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel")
    video: Mapped[Optional["Video"]] = relationship("Video")

    def __repr__(self) -> str:
        return f"<PerformanceInsight id={self.id} type={self.insight_type} severity={self.severity} is_read={self.is_read}>"
