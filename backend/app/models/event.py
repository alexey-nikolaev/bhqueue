"""Event model - represents club events (Klubnacht, etc.)"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Event(Base):
    """
    Club event entity.
    
    For MVP, we focus on Klubnacht events which run from
    Saturday 23:59 to Monday 08:00, with queue opening at 21:00.
    """
    
    __tablename__ = "events"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Event timing
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    queue_opens_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", back_populates="events")
    queue_sessions: Mapped[list["QueueSession"]] = relationship(
        "QueueSession",
        back_populates="event",
        lazy="selectin",
    )
    parsed_updates: Mapped[list["ParsedUpdate"]] = relationship(
        "ParsedUpdate",
        back_populates="event",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Event {self.name} @ {self.starts_at}>"
    
    @property
    def is_active(self) -> bool:
        """Check if the event is currently active (queue open or event running)."""
        now = datetime.utcnow()
        return self.queue_opens_at <= now <= self.ends_at
    
    @property
    def is_queue_open(self) -> bool:
        """Check if the queue is currently accepting people."""
        now = datetime.utcnow()
        return self.queue_opens_at <= now <= self.ends_at
