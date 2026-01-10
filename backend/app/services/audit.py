"""Audit service for logging and querying audit events."""

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.correlation import get_correlation_id
from app.models.audit import ActorType, AuditAction, AuditEvent
from app.schemas.audit import (
    AuditEventCreate,
    AuditEventFilter,
    AuditEventListResponse,
    AuditEventResponse,
    AuditSummary,
)

logger = structlog.get_logger(__name__)


class AuditService:
    """Service for managing audit events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        action: AuditAction | str,
        actor_type: ActorType,
        actor_id: str,
        target_type: str,
        target_id: uuid.UUID,
        library_id: Optional[uuid.UUID] = None,
        actor_name: Optional[str] = None,
        target_name: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> AuditEventResponse:
        """Log an audit event."""
        # Use provided correlation ID or get from context
        cid = correlation_id or get_correlation_id()

        event = AuditEvent.create(
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            correlation_id=cid,
            library_id=library_id,
            actor_name=actor_name,
            target_name=target_name,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        # Log to structured logger as well
        logger.info(
            "audit_event",
            event_id=str(event.id),
            action=event.action,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            target_type=event.target_type,
            target_id=str(event.target_id),
            correlation_id=str(cid),
        )

        return self._to_response(event)

    async def log_user_action(
        self,
        action: AuditAction | str,
        user_id: uuid.UUID,
        user_name: Optional[str],
        target_type: str,
        target_id: uuid.UUID,
        **kwargs,
    ) -> AuditEventResponse:
        """Convenience method to log a user action."""
        return await self.log_event(
            action=action,
            actor_type=ActorType.USER,
            actor_id=str(user_id),
            actor_name=user_name,
            target_type=target_type,
            target_id=target_id,
            **kwargs,
        )

    async def log_ai_action(
        self,
        action: AuditAction | str,
        agent_id: str,
        agent_name: Optional[str],
        target_type: str,
        target_id: uuid.UUID,
        **kwargs,
    ) -> AuditEventResponse:
        """Convenience method to log an AI agent action."""
        return await self.log_event(
            action=action,
            actor_type=ActorType.AI,
            actor_id=agent_id,
            actor_name=agent_name,
            target_type=target_type,
            target_id=target_id,
            **kwargs,
        )

    async def log_system_action(
        self,
        action: AuditAction | str,
        target_type: str,
        target_id: uuid.UUID,
        **kwargs,
    ) -> AuditEventResponse:
        """Convenience method to log a system action."""
        return await self.log_event(
            action=action,
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            actor_name="System",
            target_type=target_type,
            target_id=target_id,
            **kwargs,
        )

    async def get_events(
        self,
        filters: AuditEventFilter,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditEventListResponse:
        """Query audit events with filters."""
        conditions = []

        if filters.library_id:
            conditions.append(AuditEvent.library_id == filters.library_id)
        if filters.actor_id:
            conditions.append(AuditEvent.actor_id == filters.actor_id)
        if filters.actor_type:
            conditions.append(AuditEvent.actor_type == filters.actor_type.value)
        if filters.action:
            conditions.append(AuditEvent.action == filters.action.value)
        if filters.target_type:
            conditions.append(AuditEvent.target_type == filters.target_type)
        if filters.target_id:
            conditions.append(AuditEvent.target_id == filters.target_id)
        if filters.correlation_id:
            conditions.append(AuditEvent.correlation_id == filters.correlation_id)
        if filters.start_date:
            conditions.append(AuditEvent.timestamp >= filters.start_date)
        if filters.end_date:
            conditions.append(AuditEvent.timestamp <= filters.end_date)

        # Get total count
        count_query = select(func.count()).select_from(AuditEvent)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get events
        query = select(AuditEvent)
        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(limit)

        result = await self.db.execute(query)
        events = result.scalars().all()

        return AuditEventListResponse(
            events=[self._to_response(e) for e in events],
            total=total,
            has_more=offset + len(events) < total,
        )

    async def get_events_for_resource(
        self,
        target_type: str,
        target_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditEventListResponse:
        """Get audit events for a specific resource."""
        filters = AuditEventFilter(
            target_type=target_type,
            target_id=target_id,
        )
        return await self.get_events(filters, limit, offset)

    async def get_events_for_library(
        self,
        library_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditEventListResponse:
        """Get audit events for a specific library."""
        filters = AuditEventFilter(library_id=library_id)
        return await self.get_events(filters, limit, offset)

    async def get_events_by_correlation_id(
        self,
        correlation_id: uuid.UUID,
    ) -> list[AuditEventResponse]:
        """Get all events with a specific correlation ID."""
        query = (
            select(AuditEvent)
            .where(AuditEvent.correlation_id == correlation_id)
            .order_by(AuditEvent.timestamp.asc())
        )

        result = await self.db.execute(query)
        events = result.scalars().all()

        return [self._to_response(e) for e in events]

    async def get_summary(
        self,
        library_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> AuditSummary:
        """Get summary statistics for audit events."""
        conditions = []

        if library_id:
            conditions.append(AuditEvent.library_id == library_id)
        if start_date:
            conditions.append(AuditEvent.timestamp >= start_date)
        if end_date:
            conditions.append(AuditEvent.timestamp <= end_date)

        base_query = select(AuditEvent)
        if conditions:
            base_query = base_query.where(and_(*conditions))

        # Total count
        count_query = select(func.count()).select_from(AuditEvent)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total_result = await self.db.execute(count_query)
        total_events = total_result.scalar() or 0

        # Events by action
        action_query = (
            select(AuditEvent.action, func.count().label("count"))
            .group_by(AuditEvent.action)
        )
        if conditions:
            action_query = action_query.where(and_(*conditions))

        action_result = await self.db.execute(action_query)
        events_by_action = {row.action: row.count for row in action_result}

        # Events by actor type
        actor_query = (
            select(AuditEvent.actor_type, func.count().label("count"))
            .group_by(AuditEvent.actor_type)
        )
        if conditions:
            actor_query = actor_query.where(and_(*conditions))

        actor_result = await self.db.execute(actor_query)
        events_by_actor_type = {row.actor_type: row.count for row in actor_result}

        # Recent activity
        recent_query = base_query.order_by(AuditEvent.timestamp.desc()).limit(10)
        recent_result = await self.db.execute(recent_query)
        recent_events = recent_result.scalars().all()

        return AuditSummary(
            total_events=total_events,
            events_by_action=events_by_action,
            events_by_actor_type=events_by_actor_type,
            recent_activity=[self._to_response(e) for e in recent_events],
        )

    def _to_response(self, event: AuditEvent) -> AuditEventResponse:
        """Convert an AuditEvent model to a response schema."""
        return AuditEventResponse(
            id=event.id,
            timestamp=event.timestamp,
            action=event.action,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            actor_name=event.actor_name,
            target_type=event.target_type,
            target_id=event.target_id,
            target_name=event.target_name,
            library_id=event.library_id,
            details=event.details,
            correlation_id=event.correlation_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
        )
