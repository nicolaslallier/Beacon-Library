"""Notification model for in-app and email notifications."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid


class NotificationType(str, Enum):
    """Type of notification."""
    SHARE_RECEIVED = "share.received"
    SHARE_ACCESSED = "share.accessed"
    FILE_UPDATED = "file.updated"
    FILE_DELETED = "file.deleted"
    COMMENT_ADDED = "comment.added"
    PERMISSION_CHANGED = "permission.changed"
    SYSTEM_ALERT = "system.alert"


class NotificationChannel(str, Enum):
    """Delivery channel for notifications."""
    IN_APP = "in_app"
    EMAIL = "email"
    BOTH = "both"


class Notification(Base):
    """
    Notification model for user notifications.

    Supports:
    - In-app notifications (delivered via SSE)
    - Email notifications (sent via SMTP)
    - Read/unread status
    - i18n-ready templates
    """

    __tablename__ = "notifications"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )

    # Recipient
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Notification type
    notification_type: Mapped[NotificationType] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Delivery channel
    channel: Mapped[NotificationChannel] = mapped_column(
        String(20),
        nullable=False,
        default=NotificationChannel.IN_APP,
    )

    # Content (i18n key and parameters)
    title_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    params: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Pre-rendered content (for email or fallback)
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Related entity (for deep linking)
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Action URL (for click-through)
    action_url: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
    )

    # Status
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Email delivery status
    email_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    email_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Sender info (optional)
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    sender_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Indexes
    __table_args__ = (
        # Composite index for unread notifications query
        Index("ix_notifications_user_unread", "user_id", "is_read", "created_at"),
        # Index for email queue
        Index("ix_notifications_email_pending", "channel", "email_sent"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type='{self.notification_type}', user={self.user_id})>"

    def mark_as_read(self) -> None:
        """Mark the notification as read."""
        self.is_read = True
        self.read_at = datetime.now()

    def mark_email_sent(self) -> None:
        """Mark the email as sent."""
        self.email_sent = True
        self.email_sent_at = datetime.now()

    def mark_email_failed(self, error: str) -> None:
        """Mark the email as failed."""
        self.email_error = error

    @classmethod
    def create_share_notification(
        cls,
        user_id: uuid.UUID,
        share_id: uuid.UUID,
        sender_id: uuid.UUID,
        sender_name: str,
        item_name: str,
        channel: NotificationChannel = NotificationChannel.BOTH,
    ) -> "Notification":
        """Factory method to create a share notification."""
        return cls(
            user_id=user_id,
            notification_type=NotificationType.SHARE_RECEIVED,
            channel=channel,
            title_key="notification.share.received.title",
            message_key="notification.share.received.message",
            params={
                "sender_name": sender_name,
                "item_name": item_name,
            },
            title=f"New share from {sender_name}",
            message=f"{sender_name} shared '{item_name}' with you.",
            entity_type="share",
            entity_id=share_id,
            action_url=f"/shared/{share_id}",
            sender_id=sender_id,
            sender_name=sender_name,
        )
