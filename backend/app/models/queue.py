"""Queue model - represents different queue types at a club."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QueueType(str, Enum):
    """Types of queues at a club."""
    MAIN = "main"           # Regular entry queue
    GUESTLIST = "guestlist"  # Guestlist queue
    REENTRY = "reentry"     # Re-entry queue


class Queue(Base):
    """
    Represents a specific queue at a club.
    
    For example, Berghain has:
    - Main queue (regular entry)
    - Guestlist queue (GL)
    - Re-entry queue (for people with wristbands)
    
    Each queue has its own spatial markers.
    """
    
    __tablename__ = "queues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clubs.id"),
        nullable=False,
    )
    
    # Queue identification
    queue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "Main Queue", "Guestlist"
    description: Mapped[str | None] = mapped_column(Text)
    
    # Display order (for UI)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", back_populates="queues")
    spatial_markers: Mapped[list["SpatialMarker"]] = relationship(
        "SpatialMarker",
        back_populates="queue",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Queue {self.name} ({self.queue_type})>"
