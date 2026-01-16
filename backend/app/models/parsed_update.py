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
    
    # Club reference
    club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clubs.id"),
        nullable=False,
    )
    
    # Source tracking
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # reddit, telegram
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Original message ID
    author_name: Mapped[str | None] = mapped_column(String(100))  # Reddit/Telegram username
    
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
    parsed_wait_minutes: Mapped[int | None] = mapped_column(Integer)
    parsed_queue_length: Mapped[str | None] = mapped_column(String(50))  # e.g., "short", "long"
    parsed_spatial_marker: Mapped[str | None] = mapped_column(String(100))  # e.g., "kiosk", "wriezener"
    
    # Confidence and validation
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    source_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # When originally posted
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", back_populates="parsed_updates")
    event: Mapped["Event | None"] = relationship("Event", back_populates="parsed_updates")

    def __repr__(self) -> str:
        return f"<ParsedUpdate {self.source}:{self.source_id} - {self.parsed_wait_minutes}min>"
