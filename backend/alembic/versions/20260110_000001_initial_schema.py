"""Initial schema with all core models.

Revision ID: 001
Revises:
Create Date: 2026-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for beacon-library."""

    # Libraries table
    op.create_table(
        "libraries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("bucket_name", sa.String(63), nullable=False, unique=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("mcp_write_enabled", sa.Boolean(), nullable=False, default=False),
        sa.Column("max_file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("allowed_mime_types", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Directories table
    op.create_table(
        "directories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("library_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directories.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("path", sa.String(4096), nullable=False, index=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_directory_parent_name", "directories", ["library_id", "parent_id", "name"])
    op.create_index("ix_directories_library_path", "directories", ["library_id", "path"])

    # Files table
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("library_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("directory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directories.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("path", sa.String(4096), nullable=False, index=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False, default="application/octet-stream"),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, default=1),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("modified_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_file_directory_filename", "files", ["library_id", "directory_id", "filename"])
    op.create_index("ix_files_library_path", "files", ["library_id", "path"])
    op.create_index("ix_files_content_type", "files", ["content_type"])

    # File versions table
    op.create_table(
        "file_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.create_unique_constraint("uq_file_version_number", "file_versions", ["file_id", "version_number"])

    # Share links table
    op.create_table(
        "share_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("permission", sa.String(20), nullable=False, default="read_only"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_access_count", sa.Integer(), nullable=True),
        sa.Column("current_access_count", sa.Integer(), nullable=False, default=0),
        sa.Column("password_hash", sa.String(128), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("guest_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )

    # Audit events table
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("actor_type", sa.String(20), nullable=False, index=True),
        sa.Column("actor_id", sa.String(255), nullable=False, index=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("target_type", sa.String(50), nullable=False, index=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("target_name", sa.String(255), nullable=True),
        sa.Column("library_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_library_timestamp", "audit_events", ["library_id", "timestamp"])
    op.create_index("ix_audit_actor_timestamp", "audit_events", ["actor_id", "timestamp"])
    op.create_index("ix_audit_target_timestamp", "audit_events", ["target_type", "target_id", "timestamp"])

    # Notifications table
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("notification_type", sa.String(50), nullable=False, index=True),
        sa.Column("channel", sa.String(20), nullable=False, default="in_app"),
        sa.Column("title_key", sa.String(255), nullable=False),
        sa.Column("message_key", sa.String(255), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_url", sa.String(2048), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent", sa.Boolean(), nullable=False, default=False),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sender_name", sa.String(255), nullable=True),
    )
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "is_read", "created_at"])
    op.create_index("ix_notifications_email_pending", "notifications", ["channel", "email_sent"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("notifications")
    op.drop_table("audit_events")
    op.drop_table("share_links")
    op.drop_table("file_versions")
    op.drop_table("files")
    op.drop_table("directories")
    op.drop_table("libraries")
