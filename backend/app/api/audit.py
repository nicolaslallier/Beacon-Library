"""API endpoints for audit events."""

import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.audit import (
    ActorType,
    AuditAction,
    AuditEventFilter,
    AuditEventListResponse,
    AuditEventResponse,
    AuditSummary,
)
from app.services.audit import AuditService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])


def get_audit_service(
    db: AsyncSession = Depends(get_db),
) -> AuditService:
    """Get audit service dependency."""
    return AuditService(db=db)


@router.get(
    "",
    response_model=AuditEventListResponse,
    summary="List audit events",
    description="Query audit events with optional filters.",
)
async def list_audit_events(
    library_id: Optional[uuid.UUID] = Query(None, description="Filter by library"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    actor_type: Optional[ActorType] = Query(None, description="Filter by actor type"),
    action: Optional[AuditAction] = Query(None, description="Filter by action"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    target_id: Optional[uuid.UUID] = Query(None, description="Filter by target ID"),
    correlation_id: Optional[uuid.UUID] = Query(
        None, description="Filter by correlation ID"
    ),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of events"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
):
    """List audit events with optional filters."""
    filters = AuditEventFilter(
        library_id=library_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        target_type=target_type,
        target_id=target_id,
        correlation_id=correlation_id,
        start_date=start_date,
        end_date=end_date,
    )

    return await service.get_events(filters, limit, offset)


@router.get(
    "/resource/{target_type}/{target_id}",
    response_model=AuditEventListResponse,
    summary="Get audit events for resource",
    description="Get audit trail for a specific resource.",
)
async def get_resource_audit_events(
    target_type: str,
    target_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
):
    """Get audit events for a specific resource."""
    return await service.get_events_for_resource(
        target_type=target_type,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/library/{library_id}",
    response_model=AuditEventListResponse,
    summary="Get library audit events",
    description="Get audit trail for a specific library.",
)
async def get_library_audit_events(
    library_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
):
    """Get audit events for a specific library."""
    return await service.get_events_for_library(
        library_id=library_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/correlation/{correlation_id}",
    response_model=list[AuditEventResponse],
    summary="Get events by correlation ID",
    description="Get all events associated with a specific request/correlation ID.",
)
async def get_events_by_correlation(
    correlation_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
):
    """Get all events with a specific correlation ID."""
    return await service.get_events_by_correlation_id(correlation_id)


@router.get(
    "/summary",
    response_model=AuditSummary,
    summary="Get audit summary",
    description="Get summary statistics for audit events.",
)
async def get_audit_summary(
    library_id: Optional[uuid.UUID] = Query(None, description="Filter by library"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    current_user: dict = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
):
    """Get summary statistics for audit events."""
    return await service.get_summary(
        library_id=library_id,
        start_date=start_date,
        end_date=end_date,
    )
