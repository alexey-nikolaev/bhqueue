"""User model - app users who can submit queue updates."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuthProvider(str, Enum):
    """Authentication provider types."""
    EMAIL = "email"
    GOOGLE = "google"
    APPLE = "apple"


class User(Base):
    """
    User entity.
    
    Supports both email/password registration and OAuth providers
    (Google, Apple) for frictionless signup.
    """
    
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))  # Null for OAuth-only users
    
    # OAuth fields
    provider: Mapped[str] = mapped_column(
        String(50),
        default=AuthProvider.EMAIL.value,
        nullable=False,
    )
    provider_id: Mapped[str | None] = mapped_column(String(255))  # External OAuth ID
    
    # Profile
    display_name: Mapped[str | None] = mapped_column(String(100))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # Email verified
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    queue_sessions: Mapped[list["QueueSession"]] = relationship(
        "QueueSession",
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
