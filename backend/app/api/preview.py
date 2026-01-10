"""API endpoints for file previews."""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.file import FileMetadata
from app.services.preview import PreviewService, PREVIEWABLE_TYPES
from app.services.storage import MinIOService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/preview", tags=["preview"])


def get_preview_service() -> PreviewService:
    """Get preview service dependency."""
    return PreviewService()


def get_storage_service() -> MinIOService:
    """Get storage service dependency."""
    return MinIOService(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@router.get(
    "/supported",
    summary="Get supported preview types",
    description="Get list of MIME types that support preview.",
)
async def get_supported_types():
    """Get list of supported preview types."""
    return {
        "supported_types": list(PREVIEWABLE_TYPES.keys()),
        "max_file_size": settings.preview_max_file_size,
        "enabled": settings.preview_enabled,
    }


@router.get(
    "/file/{file_id}",
    summary="Get file preview",
    description="Generate or retrieve a preview for a file.",
)
async def get_file_preview(
    file_id: uuid.UUID,
    thumbnail: bool = Query(False, description="Return thumbnail instead of full preview"),
    width: int = Query(200, ge=50, le=1000, description="Thumbnail width"),
    height: int = Query(200, ge=50, le=1000, description="Thumbnail height"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    preview_service: PreviewService = Depends(get_preview_service),
    storage_service: MinIOService = Depends(get_storage_service),
):
    """Get a preview for a file."""
    if not settings.preview_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Preview service is disabled",
        )

    # Get file metadata
    query = select(FileMetadata).where(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.is_deleted == False,
        )
    )
    result = await db.execute(query)
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Check if preview is supported
    if not preview_service.can_preview(file.mime_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Preview not supported for {file.mime_type}",
        )

    # Check file size
    if file.size and file.size > settings.preview_max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large for preview",
        )

    try:
        # Get file content from storage
        bucket_name = f"beacon-lib-{file.library_id}"
        file_content = await storage_service.get_file_content(
            bucket_name=bucket_name,
            object_name=file.storage_key,
        )

        if thumbnail:
            # Generate thumbnail
            preview_content, preview_mime = await preview_service.generate_thumbnail(
                file_content=file_content,
                file_name=file.name,
                mime_type=file.mime_type,
                width=width,
                height=height,
            )
        else:
            # Generate full preview
            preview_content, preview_mime = await preview_service.generate_preview(
                file_content=file_content,
                file_name=file.name,
                mime_type=file.mime_type,
            )

        return Response(
            content=preview_content,
            media_type=preview_mime,
            headers={
                "Content-Disposition": f'inline; filename="preview_{file.name}"',
                "Cache-Control": "private, max-age=3600",
            },
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "preview_generation_error",
            file_id=str(file_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Preview generation failed",
        )


@router.get(
    "/check/{file_id}",
    summary="Check preview availability",
    description="Check if a preview can be generated for a file.",
)
async def check_preview_availability(
    file_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    preview_service: PreviewService = Depends(get_preview_service),
):
    """Check if preview is available for a file."""
    # Get file metadata
    query = select(FileMetadata).where(
        and_(
            FileMetadata.id == file_id,
            FileMetadata.is_deleted == False,
        )
    )
    result = await db.execute(query)
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    can_preview = preview_service.can_preview(file.mime_type)
    needs_conversion = preview_service.needs_conversion(file.mime_type)
    size_ok = not file.size or file.size <= settings.preview_max_file_size

    return {
        "file_id": str(file_id),
        "mime_type": file.mime_type,
        "can_preview": can_preview and size_ok and settings.preview_enabled,
        "needs_conversion": needs_conversion,
        "size_ok": size_ok,
        "service_enabled": settings.preview_enabled,
    }
