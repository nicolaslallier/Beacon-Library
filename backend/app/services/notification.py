"""Notification service for in-app and email notifications."""

import datetime
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiosmtplib
import structlog
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import Notification, NotificationChannel, NotificationType as ModelNotificationType
from app.schemas.notification import (
    EmailNotification,
    NotificationCreate,
    NotificationListResponse,
    NotificationResponse,
    NotificationType,
    ShareNotificationData,
)

logger = structlog.get_logger(__name__)


class NotificationService:
    """Service for managing in-app notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
        self,
        data: NotificationCreate,
    ) -> NotificationResponse:
        """Create a new notification."""
        notification = Notification(
            user_id=data.user_id,
            notification_type=data.notification_type.value,
            channel=NotificationChannel.IN_APP,
            title_key=f"notification.{data.notification_type.value}.title",
            message_key=f"notification.{data.notification_type.value}.message",
            title=data.title,
            message=data.message,
            action_url=data.action_url,
            params=data.metadata,
        )

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        logger.info(
            "notification_created",
            notification_id=str(notification.id),
            user_id=str(data.user_id),
            type=data.notification_type.value,
        )

        return self._to_response(notification)

    async def get_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> NotificationListResponse:
        """Get notifications for a user."""
        conditions = [
            Notification.user_id == user_id,
            Notification.is_deleted == False,
        ]

        if unread_only:
            conditions.append(Notification.is_read == False)

        # Get total count
        count_query = select(func.count()).select_from(Notification).where(
            and_(*conditions)
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get unread count
        unread_query = select(func.count()).select_from(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_deleted == False,
                Notification.is_read == False,
            )
        )
        unread_result = await self.db.execute(unread_query)
        unread_count = unread_result.scalar() or 0

        # Get notifications
        query = (
            select(Notification)
            .where(and_(*conditions))
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(query)
        notifications = result.scalars().all()

        return NotificationListResponse(
            notifications=[self._to_response(n) for n in notifications],
            total=total,
            unread_count=unread_count,
        )

    async def mark_as_read(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Mark a notification as read."""
        query = (
            update(Notification)
            .where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
            .values(
                is_read=True,
                read_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )

        result = await self.db.execute(query)
        await self.db.commit()

        return result.rowcount > 0

    async def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        """Mark all notifications as read for a user."""
        query = (
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                )
            )
            .values(
                is_read=True,
                read_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )

        result = await self.db.execute(query)
        await self.db.commit()

        logger.info(
            "notifications_marked_read",
            user_id=str(user_id),
            count=result.rowcount,
        )

        return result.rowcount

    async def delete_notification(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Soft delete a notification."""
        query = (
            update(Notification)
            .where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
            .values(is_deleted=True)
        )

        result = await self.db.execute(query)
        await self.db.commit()

        return result.rowcount > 0

    async def create_share_notification(
        self,
        recipient_user_id: uuid.UUID,
        data: ShareNotificationData,
    ) -> NotificationResponse:
        """Create a notification for a share event."""
        notification_data = NotificationCreate(
            user_id=recipient_user_id,
            notification_type=NotificationType.SHARE_RECEIVED,
            title=f"{data.shared_by_name} shared a {data.target_type} with you",
            message=f'"{data.target_name}" has been shared with you.',
            action_url=data.share_url,
            metadata={
                "share_id": str(data.share_id),
                "share_type": data.share_type,
                "target_type": data.target_type,
                "target_id": str(data.target_id),
                "shared_by_name": data.shared_by_name,
            },
        )

        return await self.create_notification(notification_data)

    async def create_share_access_notification(
        self,
        owner_user_id: uuid.UUID,
        share_id: uuid.UUID,
        target_name: str,
        visitor_ip: Optional[str] = None,
    ) -> NotificationResponse:
        """Create a notification when a share link is accessed."""
        notification_data = NotificationCreate(
            user_id=owner_user_id,
            notification_type=NotificationType.SHARE_ACCESSED,
            title="Your share link was accessed",
            message=f'Someone accessed your shared "{target_name}".',
            metadata={
                "share_id": str(share_id),
                "visitor_ip": visitor_ip,
            },
        )

        return await self.create_notification(notification_data)

    def _to_response(self, notification: Notification) -> NotificationResponse:
        """Convert a Notification model to a response schema."""
        from app.schemas.notification import NotificationPriority

        return NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            notification_type=notification.notification_type,
            title=notification.title or notification.title_key,
            message=notification.message or notification.message_key,
            priority=NotificationPriority.NORMAL,
            action_url=notification.action_url,
            is_read=notification.is_read,
            read_at=notification.read_at,
            created_at=notification.created_at,
            metadata=notification.params,
        )


class EmailService:
    """Service for sending email notifications."""

    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = None,
        smtp_user: str = None,
        smtp_password: str = None,
        smtp_use_tls: bool = True,
        from_email: str = None,
        from_name: str = None,
    ):
        self.smtp_host = smtp_host or settings.smtp_host
        self.smtp_port = smtp_port or settings.smtp_port
        self.smtp_user = smtp_user or settings.smtp_user
        self.smtp_password = smtp_password or settings.smtp_password
        self.smtp_use_tls = smtp_use_tls if smtp_use_tls is not None else settings.smtp_use_tls
        self.from_email = from_email or settings.smtp_from_email
        self.from_name = from_name or settings.smtp_from_name

    async def send_email(self, email: EmailNotification) -> bool:
        """Send an email notification."""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = email.subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = (
                f"{email.to_name} <{email.to_email}>"
                if email.to_name
                else email.to_email
            )

            if email.reply_to:
                msg["Reply-To"] = email.reply_to

            if email.cc:
                msg["Cc"] = ", ".join(email.cc)

            # Add text and HTML parts
            if email.body_text:
                msg.attach(MIMEText(email.body_text, "plain"))
            msg.attach(MIMEText(email.body_html, "html"))

            # Send email
            if self.smtp_use_tls:
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    start_tls=True,
                )
            else:
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                )

            logger.info(
                "email_sent",
                to=email.to_email,
                subject=email.subject,
            )

            return True

        except Exception as e:
            logger.error(
                "email_send_failed",
                to=email.to_email,
                subject=email.subject,
                error=str(e),
            )
            return False

    async def send_share_notification(
        self,
        data: ShareNotificationData,
        recipient_email: str,
        recipient_name: Optional[str] = None,
    ) -> bool:
        """Send a share notification email."""
        expiry_text = ""
        if data.expires_at:
            expiry_text = f"<p>This link expires on {data.expires_at.strftime('%B %d, %Y at %H:%M UTC')}.</p>"

        message_text = ""
        if data.message:
            message_text = f'<p><em>"{data.message}"</em></p>'

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; border-radius: 12px 12px 0 0; text-align: center; }}
                .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; }}
                .button {{ display: inline-block; background: #10b981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin: 20px 0; font-weight: 500; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
                .file-info {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">📁 New Share</h1>
                </div>
                <div class="content">
                    <p>Hi{' ' + recipient_name if recipient_name else ''},</p>
                    <p><strong>{data.shared_by_name}</strong> has shared a {data.target_type} with you:</p>

                    <div class="file-info">
                        <strong>{data.target_name}</strong><br>
                        <small style="color: #6b7280;">Access level: {data.share_type.title()}</small>
                    </div>

                    {message_text}

                    <p style="text-align: center;">
                        <a href="{data.share_url}" class="button">View Shared {data.target_type.title()}</a>
                    </p>

                    {expiry_text}
                </div>
                <div class="footer">
                    <p>This email was sent by Beacon Library</p>
                    <p>If you didn't expect this email, you can safely ignore it.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
{data.shared_by_name} has shared a {data.target_type} with you.

{data.target_name}
Access level: {data.share_type.title()}

{f'Message: {data.message}' if data.message else ''}

View it here: {data.share_url}

{f'This link expires on {data.expires_at.strftime("%B %d, %Y at %H:%M UTC")}.' if data.expires_at else ''}

---
This email was sent by Beacon Library.
        """

        email = EmailNotification(
            to_email=recipient_email,
            to_name=recipient_name,
            subject=f"{data.shared_by_name} shared \"{data.target_name}\" with you",
            body_html=html_body,
            body_text=text_body,
        )

        return await self.send_email(email)

    async def send_share_access_notification(
        self,
        owner_email: str,
        owner_name: Optional[str],
        target_name: str,
        share_url: str,
        visitor_ip: Optional[str] = None,
    ) -> bool:
        """Send an email when a share link is accessed."""
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: white; padding: 30px; border-radius: 12px 12px 0 0; text-align: center; }}
                .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
                .info-box {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">🔔 Share Link Accessed</h1>
                </div>
                <div class="content">
                    <p>Hi{' ' + owner_name if owner_name else ''},</p>
                    <p>Someone has accessed your shared file:</p>

                    <div class="info-box">
                        <strong>{target_name}</strong><br>
                        <small style="color: #6b7280;">Accessed at: {datetime.datetime.now(datetime.timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}</small>
                        {f'<br><small style="color: #6b7280;">From IP: {visitor_ip}</small>' if visitor_ip else ''}
                    </div>

                    <p>You're receiving this email because you enabled access notifications for this share link.</p>
                </div>
                <div class="footer">
                    <p>This email was sent by Beacon Library</p>
                </div>
            </div>
        </body>
        </html>
        """

        email = EmailNotification(
            to_email=owner_email,
            to_name=owner_name,
            subject=f'Your share link for "{target_name}" was accessed',
            body_html=html_body,
        )

        return await self.send_email(email)
