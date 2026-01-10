"""Library model - top-level container for files and directories."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.directory import Directory
    from app.models.file import FileMetadata


class Library(Base, TimestampMixin, SoftDeleteMixin):
    """
    Library model representing a top-level document container.

    Analogous to a SharePoint Document Library.
    Each library has its own MinIO bucket for file storage.
    """

    __tablename__ = "libraries"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Storage configuration
    bucket_name: Mapped[str] = mapped_column(
        String(63),  # S3 bucket name max length
        nullable=False,
        unique=True,
    )

    # Ownership
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # MCP configuration
    mcp_write_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Settings
    max_file_size_bytes: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        default=None,
    )
    allowed_mime_types: Mapped[Optional[str]] = mapped_column(
        Text,  # JSON array stored as text
        nullable=True,
        default=None,
    )

    # Relationships
    directories: Mapped[List["Directory"]] = relationship(
        "Directory",
        back_populates="library",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    files: Mapped[List["FileMetadata"]] = relationship(
        "FileMetadata",
        back_populates="library",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Library(id={self.id}, name='{self.name}', bucket='{self.bucket_name}')>"

    @staticmethod
    def generate_bucket_name(library_id: uuid.UUID) -> str:
        """Generate a unique bucket name for a library."""
        # S3 bucket names must be lowercase, 3-63 chars, no underscores
        return f"beacon-lib-{str(library_id).replace('-', '')[:16]}"
