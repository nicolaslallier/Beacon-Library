"""Pydantic schemas for notifications."""

import datetime
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationType(str, Enum):
    """Type of notification."""

    SHARE_RECEIVED = "share_received"
    SHARE_ACCESSED = "share_accessed"
    SHARE_EXPIRED = "share_expired"
    FILE_UPLOADED = "file_uploaded"
    FILE_DELETED = "file_deleted"
    FILE_MOVED = "file_moved"
    COMMENT_ADDED = "comment_added"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Priority level for notifications."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationBase(BaseModel):
    """Base schema for notifications."""

    notification_type: NotificationType
    title: str = Field(..., max_length=255)
    message: str = Field(..., max_length=2000)
    priority: NotificationPriority = NotificationPriority.NORMAL
    action_url: Optional[str] = Field(default=None, max_length=500)


class NotificationCreate(NotificationBase):
    """Schema for creating a notification."""

    user_id: uuid.UUID
    metadata: Optional[dict] = Field(default=None)


class NotificationResponse(NotificationBase):
    """Schema for notification responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    is_read: bool
    read_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    metadata: Optional[dict] = None


class NotificationUpdate(BaseModel):
    """Schema for updating a notification."""

    is_read: Optional[bool] = None


class NotificationListResponse(BaseModel):
    """Response for listing notifications."""

    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class EmailNotification(BaseModel):
    """Schema for email notifications."""

    to_email: str
    to_name: Optional[str] = None
    subject: str
    body_html: str
    body_text: Optional[str] = None
    reply_to: Optional[str] = None
    cc: Optional[list[str]] = None
    bcc: Optional[list[str]] = None


class ShareNotificationData(BaseModel):
    """Data for share-related notifications."""

    share_id: uuid.UUID
    share_type: str
    target_type: str
    target_id: uuid.UUID
    target_name: str
    shared_by_name: str
    shared_by_email: Optional[str] = None
    share_url: str
    expires_at: Optional[datetime.datetime] = None
    message: Optional[str] = None
