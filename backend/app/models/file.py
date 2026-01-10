"""File models - FileMetadata and FileVersion for file management."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.directory import Directory
    from app.models.library import Library


class FileMetadata(Base, TimestampMixin, SoftDeleteMixin):
    """
    FileMetadata model representing a file's metadata.

    The actual file content is stored in MinIO, referenced by storage_key.
    Supports versioning through the FileVersion relationship.
    """

    __tablename__ = "files"

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

    # Directory relationship (null for root-level files)
    directory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("directories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # File info
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Denormalized path for efficient querying
    path: Mapped[str] = mapped_column(
        String(4096),
        nullable=False,
        index=True,
    )

    # File properties
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    checksum_sha256: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hex digest
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="application/octet-stream",
    )

    # MinIO storage reference
    storage_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # Current version number
    current_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Ownership
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    modified_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    # Relationships
    library: Mapped["Library"] = relationship(
        "Library",
        back_populates="files",
    )

    directory: Mapped[Optional["Directory"]] = relationship(
        "Directory",
        back_populates="files",
    )

    versions: Mapped[List["FileVersion"]] = relationship(
        "FileVersion",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FileVersion.version_number.desc()",
        lazy="dynamic",
    )

    # Constraints
    __table_args__ = (
        # Unique constraint: no duplicate filenames in the same directory
        UniqueConstraint(
            "library_id",
            "directory_id",
            "filename",
            name="uq_file_directory_filename",
        ),
        # Index for path-based queries
        Index("ix_files_library_path", "library_id", "path"),
        # Index for content type queries
        Index("ix_files_content_type", "content_type"),
    )

    def __repr__(self) -> str:
        return f"<FileMetadata(id={self.id}, filename='{self.filename}', size={self.size_bytes})>"

    @property
    def full_path(self) -> str:
        """Return the full path including the filename."""
        if self.path == "/":
            return f"/{self.filename}"
        return f"{self.path}/{self.filename}"

    @property
    def extension(self) -> Optional[str]:
        """Return the file extension, if any."""
        if "." in self.filename:
            return self.filename.rsplit(".", 1)[-1].lower()
        return None


class FileVersion(Base):
    """
    FileVersion model for tracking file version history.

    Each version stores a reference to the file content in MinIO.
    """

    __tablename__ = "file_versions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )

    # File relationship
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Version info
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # File properties at this version
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    # MinIO storage reference for this version
    storage_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # Version metadata
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    # Optional comment describing the version
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    file: Mapped["FileMetadata"] = relationship(
        "FileMetadata",
        back_populates="versions",
    )

    # Constraints
    __table_args__ = (
        # Unique constraint: version numbers must be unique per file
        UniqueConstraint(
            "file_id",
            "version_number",
            name="uq_file_version_number",
        ),
    )

    def __repr__(self) -> str:
        return f"<FileVersion(id={self.id}, file_id={self.file_id}, version={self.version_number})>"
