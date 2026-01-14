"""Club model - represents nightclubs (Berghain, etc.)"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Club(Base):
    """
    Nightclub entity.
    
    For MVP, only Berghain is supported, but the schema supports
    adding more Berlin clubs in the future.
    """
    
    __tablename__ = "clubs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 8))
    longitude: Mapped[float | None] = mapped_column(Numeric(11, 8))
    
    # GeoJSON polygon for detecting if user is inside the club
    building_polygon: Mapped[dict | None] = mapped_column(JSONB)
    
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Berlin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    events: Mapped[list["Event"]] = relationship(
        "Event",
        back_populates="club",
        lazy="selectin",
    )
    spatial_markers: Mapped[list["SpatialMarker"]] = relationship(
        "SpatialMarker",
        back_populates="club",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Club {self.name}>"
