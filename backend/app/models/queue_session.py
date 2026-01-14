"""QueueSession model - tracks a user's journey through the queue."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QueueType(str, Enum):
    """Types of queues at Berghain."""
    MAIN = "main"
    GUEST_LIST = "guest_list"
    REENTRY = "reentry"


class QueueResult(str, Enum):
    """Possible outcomes after waiting in queue."""
    ADMITTED = "admitted"
    REJECTED = "rejected"
    LEFT = "left"  # User left voluntarily


class QueueSession(Base):
    """
    Tracks a user's queue experience from joining to result.
    
    Records when they joined, their position updates, and the final
    outcome (admitted, rejected, or left).
    """
    
    __tablename__ = "queue_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id"),
        nullable=False,
    )
    
    # Queue type (MVP: main only)
    queue_type: Mapped[str] = mapped_column(
        String(20),
        default=QueueType.MAIN.value,
        nullable=False,
    )
    
    # Timing
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    result_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Outcome
    result: Mapped[str | None] = mapped_column(String(20))  # admitted, rejected, left
    
    # GPS-based detection
    is_inside_club: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="queue_sessions")
    event: Mapped["Event"] = relationship("Event", back_populates="queue_sessions")
    position_updates: Mapped[list["PositionUpdate"]] = relationship(
        "PositionUpdate",
        back_populates="session",
        lazy="selectin",
        order_by="PositionUpdate.recorded_at",
    )

    def __repr__(self) -> str:
        return f"<QueueSession {self.id} - {self.result or 'in_queue'}>"
    
    @property
    def is_complete(self) -> bool:
        """Check if the queue session has ended."""
        return self.result is not None or self.is_inside_club
    
    @property
    def wait_duration_minutes(self) -> int | None:
        """Calculate total wait time in minutes."""
        if not self.result_at:
            return None
        delta = self.result_at - self.joined_at
        return int(delta.total_seconds() / 60)
