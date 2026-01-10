"""Share link model for file and directory sharing."""

import secrets
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid


class ShareTargetType(str, Enum):
    """Type of target being shared."""
    FILE = "file"
    DIRECTORY = "directory"
    LIBRARY = "library"


class ShareType(str, Enum):
    """Type of share permission."""
    VIEW = "view"
    DOWNLOAD = "download"
    EDIT = "edit"


class ShareLink(Base):
    """
    ShareLink model for sharing files, directories, and libraries.

    Supports:
    - Different permission levels (view, download, edit)
    - Time-based expiry
    - Access count limits
    - Optional password protection
    - Keycloak guest account integration
    - Access notifications
    """

    __tablename__ = "share_links"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )

    # High-entropy unguessable token
    token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    # Share type (permission level)
    share_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ShareType.VIEW.value,
    )

    # Target reference
    target_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Ownership
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Password protection (hash with salt)
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
    )

    # Expiry settings
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    max_access_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Access tracking
    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Guest access settings
    allow_guest_access: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    guest_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Notification settings
    notify_on_access: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Optional name/description for the share
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ShareLink(id={self.id}, target={self.target_type}:{self.target_id})>"

    @staticmethod
    def generate_token() -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(48)

    def check_expired(self) -> bool:
        """Check if the share link has expired."""
        from datetime import timezone

        if not self.is_active:
            return True
        if self.expires_at is not None and datetime.now(timezone.utc) > self.expires_at:
            return True
        if self.max_access_count is not None and self.access_count >= self.max_access_count:
            return True
        return False

    def increment_access_count(self) -> None:
        """Increment the access counter."""
        from datetime import timezone

        self.access_count += 1
        self.last_accessed_at = datetime.now(timezone.utc)

    def revoke(self) -> None:
        """Revoke the share link."""
        self.is_active = False
