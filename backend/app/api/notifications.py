"""API endpoints for notifications."""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    NotificationUpdate,
)
from app.services.notification import NotificationService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(
    db: AsyncSession = Depends(get_db),
) -> NotificationService:
    """Get notification service dependency."""
    return NotificationService(db=db)


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications",
    description="Get notifications for the current user.",
)
async def list_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of notifications"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """List notifications for the current user."""
    return await service.get_notifications(
        user_id=uuid.UUID(current_user["sub"]),
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark notification as read",
    description="Mark a specific notification as read.",
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """Mark a notification as read."""
    success = await service.mark_as_read(
        notification_id=notification_id,
        user_id=uuid.UUID(current_user["sub"]),
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )


@router.post(
    "/read-all",
    status_code=status.HTTP_200_OK,
    summary="Mark all as read",
    description="Mark all notifications as read for the current user.",
)
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """Mark all notifications as read."""
    count = await service.mark_all_as_read(
        user_id=uuid.UUID(current_user["sub"]),
    )
    return {"marked_read": count}


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
    description="Delete a specific notification.",
)
async def delete_notification(
    notification_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """Delete a notification."""
    success = await service.delete_notification(
        notification_id=notification_id,
        user_id=uuid.UUID(current_user["sub"]),
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
