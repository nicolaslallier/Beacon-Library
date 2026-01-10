"""API endpoints for real-time updates via SSE."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Set

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/realtime", tags=["realtime"])


# In-memory event bus (for single-server deployment)
# For production with multiple servers, use Redis Pub/Sub
class EventBus:
    """Simple in-memory event bus for real-time updates."""

    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._user_subscriptions: Dict[str, Set[str]] = {}

    def subscribe(self, channel: str, user_id: str) -> asyncio.Queue:
        """Subscribe to a channel."""
        if channel not in self._subscribers:
            self._subscribers[channel] = set()

        queue = asyncio.Queue()
        self._subscribers[channel].add(queue)

        # Track user subscriptions
        if user_id not in self._user_subscriptions:
            self._user_subscriptions[user_id] = set()
        self._user_subscriptions[user_id].add(channel)

        logger.info(
            "realtime_subscribe",
            channel=channel,
            user_id=user_id,
        )

        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue, user_id: str):
        """Unsubscribe from a channel."""
        if channel in self._subscribers:
            self._subscribers[channel].discard(queue)
            if not self._subscribers[channel]:
                del self._subscribers[channel]

        if user_id in self._user_subscriptions:
            self._user_subscriptions[user_id].discard(channel)

        logger.info(
            "realtime_unsubscribe",
            channel=channel,
            user_id=user_id,
        )

    async def publish(self, channel: str, event_type: str, data: dict):
        """Publish an event to a channel."""
        if channel not in self._subscribers:
            return

        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for queue in self._subscribers[channel]:
            try:
                await queue.put(event)
            except Exception as e:
                logger.error(
                    "realtime_publish_error",
                    channel=channel,
                    error=str(e),
                )

    async def publish_to_user(self, user_id: str, event_type: str, data: dict):
        """Publish an event to all channels a user is subscribed to."""
        if user_id not in self._user_subscriptions:
            return

        for channel in self._user_subscriptions[user_id]:
            await self.publish(channel, event_type, data)


# Global event bus instance
event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus."""
    return event_bus


# Event types
class EventTypes:
    """Constants for real-time event types."""

    # File events
    FILE_CREATED = "file.created"
    FILE_UPDATED = "file.updated"
    FILE_DELETED = "file.deleted"
    FILE_MOVED = "file.moved"
    FILE_RENAMED = "file.renamed"

    # Directory events
    DIRECTORY_CREATED = "directory.created"
    DIRECTORY_UPDATED = "directory.updated"
    DIRECTORY_DELETED = "directory.deleted"
    DIRECTORY_MOVED = "directory.moved"
    DIRECTORY_RENAMED = "directory.renamed"

    # Share events
    SHARE_CREATED = "share.created"
    SHARE_ACCESSED = "share.accessed"
    SHARE_REVOKED = "share.revoked"

    # Notification events
    NOTIFICATION_NEW = "notification.new"
    NOTIFICATION_READ = "notification.read"

    # Sync events
    SYNC_STARTED = "sync.started"
    SYNC_COMPLETED = "sync.completed"
    SYNC_ERROR = "sync.error"


@router.get(
    "/events",
    summary="Subscribe to events",
    description="Subscribe to real-time events via Server-Sent Events.",
)
async def subscribe_to_events(
    request: Request,
    library_id: Optional[uuid.UUID] = Query(None, description="Subscribe to library events"),
    current_user: dict = Depends(get_current_user),
):
    """Subscribe to real-time events via SSE."""
    user_id = current_user["sub"]

    # Determine channel
    if library_id:
        channel = f"library:{library_id}"
    else:
        channel = f"user:{user_id}"

    queue = event_bus.subscribe(channel, user_id)

    async def event_generator():
        """Generate SSE events."""
        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "channel": channel,
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }),
            }

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for events with timeout for heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)

                    yield {
                        "event": event["type"],
                        "data": json.dumps(event["data"]),
                    }

                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }),
                    }

        finally:
            event_bus.unsubscribe(channel, queue, user_id)

    return EventSourceResponse(event_generator())


@router.post(
    "/publish",
    summary="Publish event (internal)",
    description="Publish an event to a channel. For internal use only.",
)
async def publish_event(
    channel: str,
    event_type: str,
    data: dict,
    current_user: dict = Depends(get_current_user),
):
    """Publish an event to a channel.

    Note: In production, this should be restricted to internal services.
    """
    await event_bus.publish(channel, event_type, data)
    return {"status": "published", "channel": channel, "event_type": event_type}


# Helper functions for publishing events from other services

async def publish_file_event(
    library_id: uuid.UUID,
    event_type: str,
    file_id: uuid.UUID,
    file_name: str,
    user_id: str,
    **extra_data,
):
    """Publish a file-related event."""
    await event_bus.publish(
        channel=f"library:{library_id}",
        event_type=event_type,
        data={
            "file_id": str(file_id),
            "file_name": file_name,
            "library_id": str(library_id),
            "user_id": user_id,
            **extra_data,
        },
    )


async def publish_directory_event(
    library_id: uuid.UUID,
    event_type: str,
    directory_id: uuid.UUID,
    directory_name: str,
    user_id: str,
    **extra_data,
):
    """Publish a directory-related event."""
    await event_bus.publish(
        channel=f"library:{library_id}",
        event_type=event_type,
        data={
            "directory_id": str(directory_id),
            "directory_name": directory_name,
            "library_id": str(library_id),
            "user_id": user_id,
            **extra_data,
        },
    )


async def publish_notification_event(
    user_id: str,
    notification_id: uuid.UUID,
    notification_type: str,
    title: str,
    message: str,
):
    """Publish a notification event to a user."""
    await event_bus.publish(
        channel=f"user:{user_id}",
        event_type=EventTypes.NOTIFICATION_NEW,
        data={
            "notification_id": str(notification_id),
            "notification_type": notification_type,
            "title": title,
            "message": message,
        },
    )
