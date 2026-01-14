"""HistoricalStats model - aggregated historical queue data."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HistoricalStats(Base):
    """
    Aggregated historical statistics for queue estimation.
    
    Used to predict wait times based on day of week and hour.
    Updated periodically from completed queue sessions.
    """
    
    __tablename__ = "historical_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Time slot (0-6 for day, 0-23 for hour)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-23
    
    # Aggregated metrics
    avg_wait_minutes: Mapped[float | None] = mapped_column(Float)
    avg_queue_length_meters: Mapped[float | None] = mapped_column(Float)
    rejection_rate: Mapped[float | None] = mapped_column(Float)  # 0.0 to 1.0
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Last update
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return f"<HistoricalStats {days[self.day_of_week]} {self.hour_of_day}:00>"
