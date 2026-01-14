"""ParsedUpdate model - queue updates parsed from Reddit/Telegram."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DataSource(str, Enum):
    """Sources of parsed queue updates."""
    REDDIT = "reddit"
    TELEGRAM = "telegram"


class ParsedUpdate(Base):
    """
    Queue update parsed from Reddit or Telegram.
    
    Contains the raw message text and our extracted/parsed data
    including estimated wait time and spatial markers.
    """
    
    __tablename__ = "parsed_updates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Source tracking
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # reddit, telegram
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Original message ID
    
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id"),
    )
    
    # Queue type (parsed from message)
    queue_type: Mapped[str] = mapped_column(
        String(20),
        default="main",
        nullable=False,
    )
    
    # Raw content
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Parsed data
    estimated_wait_minutes: Mapped[int | None] = mapped_column(Integer)
    spatial_marker: Mapped[str | None] = mapped_column(String(100))  # e.g., "kiosk", "bridge"
    
    # Confidence and validation
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    event: Mapped["Event | None"] = relationship("Event", back_populates="parsed_updates")

    def __repr__(self) -> str:
        return f"<ParsedUpdate {self.source}:{self.source_id} - {self.estimated_wait_minutes}min>"
