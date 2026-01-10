"""Pydantic schemas for audit events."""

import datetime
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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


class AuditEventBase(BaseModel):
    """Base schema for audit events."""

    action: AuditAction
    actor_type: ActorType
    actor_id: str
    actor_name: Optional[str] = None
    target_type: str
    target_id: uuid.UUID
    target_name: Optional[str] = None
    library_id: Optional[uuid.UUID] = None
    details: Optional[dict] = None


class AuditEventCreate(AuditEventBase):
    """Schema for creating an audit event."""

    correlation_id: uuid.UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditEventResponse(AuditEventBase):
    """Schema for audit event responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime.datetime
    correlation_id: uuid.UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditEventListResponse(BaseModel):
    """Response for listing audit events."""

    events: list[AuditEventResponse]
    total: int
    has_more: bool


class AuditEventFilter(BaseModel):
    """Filter options for querying audit events."""

    library_id: Optional[uuid.UUID] = None
    actor_id: Optional[str] = None
    actor_type: Optional[ActorType] = None
    action: Optional[AuditAction] = None
    target_type: Optional[str] = None
    target_id: Optional[uuid.UUID] = None
    correlation_id: Optional[uuid.UUID] = None
    start_date: Optional[datetime.datetime] = None
    end_date: Optional[datetime.datetime] = None


class AuditSummary(BaseModel):
    """Summary statistics for audit events."""

    total_events: int
    events_by_action: dict[str, int]
    events_by_actor_type: dict[str, int]
    recent_activity: list[AuditEventResponse]
