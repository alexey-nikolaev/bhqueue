"""PositionUpdate model - GPS position updates from users in queue."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PositionUpdate(Base):
    """
    GPS position update from a user in the queue.
    
    Used to:
    - Track queue movement speed
    - Estimate queue length
    - Detect when user enters the club
    """
    
    __tablename__ = "position_updates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queue_sessions.id"),
        nullable=False,
    )
    
    # GPS coordinates
    latitude: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(11, 8), nullable=False)
    accuracy_meters: Mapped[float | None] = mapped_column(Float)
    
    # When the position was recorded (device time)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # When we received it (server time)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    session: Mapped["QueueSession"] = relationship(
        "QueueSession",
        back_populates="position_updates",
    )

    def __repr__(self) -> str:
        return f"<PositionUpdate {self.latitude}, {self.longitude} @ {self.recorded_at}>"
