"""Audit event model for tracking all state-changing actions."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid


class ActorType(str, Enum):
    """Type of actor performing the action."""
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class AuditAction(str, Enum):
    """Types of auditable actions."""
    # Library actions
    LIBRARY_CREATE = "library.create"
    LIBRARY_UPDATE = "library.update"
    LIBRARY_DELETE = "library.delete"

    # Directory actions
    DIRECTORY_CREATE = "directory.create"
    DIRECTORY_RENAME = "directory.rename"
    DIRECTORY_MOVE = "directory.move"
    DIRECTORY_DELETE = "directory.delete"
    DIRECTORY_RESTORE = "directory.restore"

    # File actions
    FILE_UPLOAD = "file.upload"
    FILE_DOWNLOAD = "file.download"
    FILE_UPDATE = "file.update"
    FILE_RENAME = "file.rename"
    FILE_MOVE = "file.move"
    FILE_DELETE = "file.delete"
    FILE_RESTORE = "file.restore"
    FILE_VERSION_CREATE = "file.version.create"
    FILE_VERSION_RESTORE = "file.version.restore"

    # Share actions
    SHARE_CREATE = "share.create"
    SHARE_ACCESS = "share.access"
    SHARE_REVOKE = "share.revoke"

    # Permission actions
    PERMISSION_GRANT = "permission.grant"
    PERMISSION_REVOKE = "permission.revoke"

    # MCP actions
    MCP_READ = "mcp.read"
    MCP_WRITE = "mcp.write"
    MCP_POLICY_CHANGE = "mcp.policy.change"


class AuditEvent(Base):
    """
    AuditEvent model for immutable audit logging.

    Records all state-changing actions with:
    - Actor information (user, AI agent, or system)
    - Action type
    - Target entity
    - Additional context in JSONB
    - Correlation ID for request tracing
    """

    __tablename__ = "audit_events"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )

    # Timestamp (immutable)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Actor information
    actor_type: Mapped[ActorType] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str] = mapped_column(
        String(255),  # Can be UUID for users or agent identifier for AI
        nullable=False,
        index=True,
    )
    actor_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Action
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Target
    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    target_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Library context (for filtering)
    library_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Additional context
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Request correlation
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Client information
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Indexes
    __table_args__ = (
        # Composite index for common query patterns
        Index("ix_audit_library_timestamp", "library_id", "timestamp"),
        Index("ix_audit_actor_timestamp", "actor_id", "timestamp"),
        Index("ix_audit_target_timestamp", "target_type", "target_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, action='{self.action}', actor={self.actor_type}:{self.actor_id})>"

    @classmethod
    def create(
        cls,
        action: AuditAction | str,
        actor_type: ActorType,
        actor_id: str,
        target_type: str,
        target_id: uuid.UUID,
        correlation_id: uuid.UUID,
        library_id: Optional[uuid.UUID] = None,
        actor_name: Optional[str] = None,
        target_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> "AuditEvent":
        """Factory method to create an audit event."""
        return cls(
            action=action.value if isinstance(action, AuditAction) else action,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            library_id=library_id,
            details=details,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
