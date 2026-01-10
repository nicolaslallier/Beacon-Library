"""Directory model - hierarchical folder structure within a library."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.file import FileMetadata
    from app.models.library import Library


class Directory(Base, TimestampMixin, SoftDeleteMixin):
    """
    Directory model representing a folder within a library.

    Supports hierarchical structure via parent_id self-reference.
    Path is stored denormalized for efficient querying.
    """

    __tablename__ = "directories"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )

    # Library relationship
    library_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Parent directory (null for root-level directories)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("directories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Directory info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Denormalized path for efficient querying (e.g., "/documents/reports/2024")
    path: Mapped[str] = mapped_column(
        String(4096),
        nullable=False,
        index=True,
    )

    # Ownership
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    # Relationships
    library: Mapped["Library"] = relationship(
        "Library",
        back_populates="directories",
    )

    parent: Mapped[Optional["Directory"]] = relationship(
        "Directory",
        remote_side="Directory.id",
        back_populates="children",
        foreign_keys=[parent_id],
    )

    children: Mapped[List["Directory"]] = relationship(
        "Directory",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    files: Mapped[List["FileMetadata"]] = relationship(
        "FileMetadata",
        back_populates="directory",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Constraints
    __table_args__ = (
        # Unique constraint: no duplicate names in the same parent
        UniqueConstraint(
            "library_id",
            "parent_id",
            "name",
            name="uq_directory_parent_name",
        ),
        # Index for path-based queries
        Index("ix_directories_library_path", "library_id", "path"),
    )

    def __repr__(self) -> str:
        return f"<Directory(id={self.id}, name='{self.name}', path='{self.path}')>"

    @property
    def full_path(self) -> str:
        """Return the full path including the directory name."""
        if self.path == "/":
            return f"/{self.name}"
        return f"{self.path}/{self.name}"

    def build_path(self) -> str:
        """Build the path by traversing parent directories."""
        if self.parent is None:
            return "/"
        return self.parent.full_path
