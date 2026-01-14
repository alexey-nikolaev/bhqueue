"""SpatialMarker model - landmarks used to describe queue position."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SpatialMarker(Base):
    """
    Landmark/reference point used to describe queue position.
    
    People describe the queue end using landmarks like:
    - "Queue is to the kiosk"
    - "Reaching the Späti"
    - "Past the bridge"
    
    We map these to GPS coordinates and historical wait times.
    """
    
    __tablename__ = "spatial_markers"

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
    
    # Name and aliases (for text matching)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(String))  # Alternative names
    
    # Location
    latitude: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(11, 8), nullable=False)
    
    # Queue metrics
    distance_from_door_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    typical_wait_minutes: Mapped[int | None] = mapped_column(Integer)  # Historical average
    
    # Display order (for visualization)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", back_populates="spatial_markers")

    def __repr__(self) -> str:
        return f"<SpatialMarker {self.name} ({self.distance_from_door_meters}m)>"
