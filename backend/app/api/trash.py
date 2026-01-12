"""API endpoints for trash/recycle bin operations."""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.trash import (
    EmptyTrashResponse,
    PermanentDeleteRequest,
    RestoreRequest,
    RestoreResponse,
    TrashItemType,
    TrashListResponse,
)
from app.services.audit import AuditService
from app.services.storage import StorageService
from app.services.trash import TrashService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/trash", tags=["trash"])


def get_trash_service(
    db: AsyncSession = Depends(get_db),
) -> TrashService:
    """Get trash service dependency."""
    audit_service = AuditService(db=db)
    return TrashService(db=db, audit=audit_service)


@router.get(
    "",
    response_model=TrashListResponse,
    summary="List trash items",
    description="Get all items in the trash/recycle bin.",
)
async def list_trash_items(
    library_id: Optional[uuid.UUID] = Query(None, description="Filter by library"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of items"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(get_current_user),
    service: TrashService = Depends(get_trash_service),
):
    """List all items in trash."""
    return await service.get_trash_items(
        library_id=library_id,
        user_id=uuid.UUID(current_user["sub"]),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/restore",
    response_model=RestoreResponse,
    summary="Restore from trash",
    description="Restore an item from trash to its original location or a new location.",
)
async def restore_item(
    request: RestoreRequest,
    current_user: dict = Depends(get_current_user),
    service: TrashService = Depends(get_trash_service),
):
    """Restore an item from trash."""
    try:
        return await service.restore_item(
            request=request,
            user_id=uuid.UUID(current_user["sub"]),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{item_type}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete",
    description="Permanently delete an item from trash. This cannot be undone.",
)
async def permanent_delete_item(
    item_type: TrashItemType,
    item_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: TrashService = Depends(get_trash_service),
):
    """Permanently delete an item from trash."""
    success = await service.permanent_delete(
        item_type=item_type,
        item_id=item_id,
        user_id=uuid.UUID(current_user["sub"]),
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found in trash",
        )


@router.delete(
    "",
    response_model=EmptyTrashResponse,
    summary="Empty trash",
    description="Permanently delete all items from trash. This cannot be undone.",
)
async def empty_trash(
    library_id: Optional[uuid.UUID] = Query(None, description="Empty trash for specific library"),
    current_user: dict = Depends(get_current_user),
    service: TrashService = Depends(get_trash_service),
):
    """Empty all items from trash."""
    return await service.empty_trash(
        library_id=library_id,
        user_id=uuid.UUID(current_user["sub"]),
    )
