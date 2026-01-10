"""API routes for library management."""

import uuid
from typing import List

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import (
    Cache,
    CurrentUser,
    DbSession,
    LibraryDep,
    Pagination,
    Storage,
)
from app.models import Library, FileMetadata
from app.schemas.library import (
    LibraryCreate,
    LibraryListResponse,
    LibraryResponse,
    LibraryUpdate,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=LibraryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new library",
)
async def create_library(
    data: LibraryCreate,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
    cache: Cache,
) -> LibraryResponse:
    """
    Create a new document library.

    Creates a corresponding MinIO bucket for file storage.
    """
    # Generate library ID and bucket name
    library_id = uuid.uuid4()
    bucket_name = Library.generate_bucket_name(library_id)

    # Create the library record
    library = Library(
        id=library_id,
        name=data.name,
        description=data.description,
        bucket_name=bucket_name,
        created_by=user.user_id,
        owner_id=user.user_id,
        mcp_write_enabled=data.mcp_write_enabled,
        max_file_size_bytes=data.max_file_size_bytes,
    )

    db.add(library)

    # Create the MinIO bucket
    try:
        await storage.create_bucket(bucket_name)
    except Exception as e:
        logger.error("bucket_creation_failed", bucket=bucket_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create storage bucket",
        )

    await db.commit()
    await db.refresh(library)

    # Invalidate cache
    await cache.invalidate_library(library_id)

    logger.info(
        "library_created",
        library_id=str(library_id),
        name=data.name,
        user_id=str(user.user_id),
    )

    return LibraryResponse(
        id=library.id,
        name=library.name,
        description=library.description,
        bucket_name=library.bucket_name,
        owner_id=library.owner_id,
        created_by=library.created_by,
        mcp_write_enabled=library.mcp_write_enabled,
        max_file_size_bytes=library.max_file_size_bytes,
        created_at=library.created_at,
        updated_at=library.updated_at,
        file_count=0,
        total_size_bytes=0,
    )


@router.get(
    "",
    response_model=LibraryListResponse,
    summary="List all libraries",
)
async def list_libraries(
    db: DbSession,
    user: CurrentUser,
    pagination: Pagination,
) -> LibraryListResponse:
    """
    List all libraries accessible to the current user.

    Admins see all libraries, users see only their own.
    """
    # Build query
    query = select(Library).where(Library.is_deleted == False)

    # Non-admins only see their own libraries
    if not user.is_admin:
        query = query.where(Library.owner_id == user.user_id)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.offset(pagination.offset).limit(pagination.page_size)
    query = query.order_by(Library.name)

    result = await db.execute(query)
    libraries = result.scalars().all()

    # Get file counts and sizes for each library
    items = []
    for lib in libraries:
        # Get stats
        stats_query = select(
            func.count(FileMetadata.id),
            func.coalesce(func.sum(FileMetadata.size_bytes), 0),
        ).where(
            FileMetadata.library_id == lib.id,
            FileMetadata.is_deleted == False,
        )
        stats = (await db.execute(stats_query)).one()

        items.append(LibraryResponse(
            id=lib.id,
            name=lib.name,
            description=lib.description,
            bucket_name=lib.bucket_name,
            owner_id=lib.owner_id,
            created_by=lib.created_by,
            mcp_write_enabled=lib.mcp_write_enabled,
            max_file_size_bytes=lib.max_file_size_bytes,
            created_at=lib.created_at,
            updated_at=lib.updated_at,
            file_count=stats[0],
            total_size_bytes=stats[1],
        ))

    return LibraryListResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        has_more=(pagination.offset + len(items)) < total,
    )


@router.get(
    "/{library_id}",
    response_model=LibraryResponse,
    summary="Get library details",
)
async def get_library(
    library: LibraryDep,
    db: DbSession,
) -> LibraryResponse:
    """Get details of a specific library."""
    # Get stats
    stats_query = select(
        func.count(FileMetadata.id),
        func.coalesce(func.sum(FileMetadata.size_bytes), 0),
    ).where(
        FileMetadata.library_id == library.id,
        FileMetadata.is_deleted == False,
    )
    stats = (await db.execute(stats_query)).one()

    return LibraryResponse(
        id=library.id,
        name=library.name,
        description=library.description,
        bucket_name=library.bucket_name,
        owner_id=library.owner_id,
        created_by=library.created_by,
        mcp_write_enabled=library.mcp_write_enabled,
        max_file_size_bytes=library.max_file_size_bytes,
        created_at=library.created_at,
        updated_at=library.updated_at,
        file_count=stats[0],
        total_size_bytes=stats[1],
    )


@router.patch(
    "/{library_id}",
    response_model=LibraryResponse,
    summary="Update library",
)
async def update_library(
    library: LibraryDep,
    data: LibraryUpdate,
    db: DbSession,
    user: CurrentUser,
    cache: Cache,
) -> LibraryResponse:
    """Update library settings."""
    # Check ownership
    if library.owner_id != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can update this library",
        )

    # Update fields
    if data.name is not None:
        library.name = data.name
    if data.description is not None:
        library.description = data.description
    if data.mcp_write_enabled is not None:
        library.mcp_write_enabled = data.mcp_write_enabled
    if data.max_file_size_bytes is not None:
        library.max_file_size_bytes = data.max_file_size_bytes

    await db.commit()
    await db.refresh(library)

    # Invalidate cache
    await cache.invalidate_library(library.id)

    logger.info(
        "library_updated",
        library_id=str(library.id),
        user_id=str(user.user_id),
    )

    return await get_library(library, db)


@router.delete(
    "/{library_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete library",
)
async def delete_library(
    library: LibraryDep,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
    cache: Cache,
) -> None:
    """
    Soft delete a library.

    The library and all its contents are marked as deleted but not
    permanently removed until the trash retention period expires.
    """
    # Check ownership
    if library.owner_id != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete this library",
        )

    # Soft delete
    library.soft_delete(user.user_id)

    await db.commit()

    # Invalidate cache
    await cache.invalidate_library_cache(library.id)

    logger.info(
        "library_deleted",
        library_id=str(library.id),
        user_id=str(user.user_id),
    )
