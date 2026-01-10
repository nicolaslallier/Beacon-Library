"""API routes for browsing library contents."""

import uuid
from typing import List, Optional

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import asc, desc, func, select

from app.api.deps import (
    Cache,
    CurrentUser,
    DbSession,
    LibraryDep,
    Pagination,
    Sort,
)
from app.models import Directory, FileMetadata
from app.schemas.browse import BrowseItem, BrowseResponse, ItemType

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=BrowseResponse,
    summary="Browse library contents",
)
async def browse_library(
    library_id: uuid.UUID,
    library: LibraryDep,
    db: DbSession,
    user: CurrentUser,
    cache: Cache,
    pagination: Pagination,
    sort: Sort,
    path: str = Query("/", description="Directory path to browse"),
    directory_id: Optional[uuid.UUID] = Query(None, description="Directory ID to browse"),
) -> BrowseResponse:
    """
    Browse the contents of a library directory.

    Can browse by path or directory_id. Returns directories and files
    with pagination and sorting.
    """
    # Try cache first
    cached = await cache.get_directory_listing(library_id, path)
    # Skip cache for now to ensure fresh data

    # Resolve directory
    parent_id: Optional[uuid.UUID] = None
    current_path = "/"

    if directory_id:
        result = await db.execute(
            select(Directory).where(
                Directory.id == directory_id,
                Directory.library_id == library_id,
                Directory.is_deleted == False,
            )
        )
        directory = result.scalar_one_or_none()
        if directory:
            parent_id = directory.id
            current_path = directory.full_path
    elif path and path != "/":
        # Find directory by path
        result = await db.execute(
            select(Directory).where(
                Directory.library_id == library_id,
                Directory.path == path.rsplit("/", 1)[0] if "/" in path[1:] else "/",
                Directory.name == path.rsplit("/", 1)[-1],
                Directory.is_deleted == False,
            )
        )
        directory = result.scalar_one_or_none()
        if directory:
            parent_id = directory.id
            current_path = directory.full_path

    # Build breadcrumb
    breadcrumb = _build_breadcrumb(current_path, library_id)

    # Query directories
    dir_query = select(Directory).where(
        Directory.library_id == library_id,
        Directory.parent_id == parent_id,
        Directory.is_deleted == False,
    )

    # Query files
    file_query = select(FileMetadata).where(
        FileMetadata.library_id == library_id,
        FileMetadata.directory_id == parent_id,
        FileMetadata.is_deleted == False,
    )

    # Count totals
    dir_count = (await db.execute(
        select(func.count()).select_from(dir_query.subquery())
    )).scalar() or 0

    file_count = (await db.execute(
        select(func.count()).select_from(file_query.subquery())
    )).scalar() or 0

    total = dir_count + file_count

    # Apply sorting
    sort_column = _get_sort_column(sort.sort_by, Directory)
    order_func = desc if sort.is_descending else asc

    dir_query = dir_query.order_by(order_func(sort_column))

    file_sort_column = _get_sort_column(sort.sort_by, FileMetadata)
    file_query = file_query.order_by(order_func(file_sort_column))

    # Fetch items with pagination
    items: List[BrowseItem] = []

    # Directories first (unless sorting by size)
    if sort.sort_by != "size":
        # Get directories
        if pagination.offset < dir_count:
            dir_limit = min(pagination.page_size, dir_count - pagination.offset)
            result = await db.execute(
                dir_query.offset(pagination.offset).limit(dir_limit)
            )
            directories = result.scalars().all()

            for d in directories:
                # Count items in directory
                child_count = await _count_directory_items(db, d.id)

                items.append(BrowseItem(
                    id=d.id,
                    name=d.name,
                    type=ItemType.DIRECTORY,
                    path=d.full_path,
                    created_at=d.created_at,
                    updated_at=d.updated_at,
                    created_by=d.created_by,
                    item_count=child_count,
                ))

        # Get files if we have room
        remaining = pagination.page_size - len(items)
        if remaining > 0:
            file_offset = max(0, pagination.offset - dir_count)
            result = await db.execute(
                file_query.offset(file_offset).limit(remaining)
            )
            files = result.scalars().all()

            for f in files:
                items.append(BrowseItem(
                    id=f.id,
                    name=f.filename,
                    type=ItemType.FILE,
                    path=f.full_path,
                    created_at=f.created_at,
                    updated_at=f.updated_at,
                    created_by=f.created_by,
                    size_bytes=f.size_bytes,
                    content_type=f.content_type,
                    checksum_sha256=f.checksum_sha256,
                    current_version=f.current_version,
                ))
    else:
        # Sort by size - only files have size
        result = await db.execute(
            file_query.offset(pagination.offset).limit(pagination.page_size)
        )
        files = result.scalars().all()

        for f in files:
            items.append(BrowseItem(
                id=f.id,
                name=f.filename,
                type=ItemType.FILE,
                path=f.full_path,
                created_at=f.created_at,
                updated_at=f.updated_at,
                created_by=f.created_by,
                size_bytes=f.size_bytes,
                content_type=f.content_type,
                checksum_sha256=f.checksum_sha256,
                current_version=f.current_version,
            ))

    response = BrowseResponse(
        library_id=library_id,
        path=current_path,
        parent_id=parent_id,
        breadcrumb=breadcrumb,
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        has_more=(pagination.offset + len(items)) < total,
        sort_by=sort.sort_by,
        sort_order=sort.sort_order,
    )

    # Cache the result
    # await cache.set_directory_listing(library_id, current_path, [item.model_dump() for item in items])

    return response


def _build_breadcrumb(path: str, library_id: uuid.UUID) -> List[dict]:
    """Build breadcrumb navigation from path."""
    if path == "/" or not path:
        return [{"name": "Root", "path": "/", "id": None}]

    breadcrumb = [{"name": "Root", "path": "/", "id": None}]

    parts = path.strip("/").split("/")
    current_path = ""

    for part in parts:
        current_path += f"/{part}"
        breadcrumb.append({
            "name": part,
            "path": current_path,
            "id": None,  # Would need DB lookup for IDs
        })

    return breadcrumb


def _get_sort_column(sort_by: str, model):
    """Get the SQLAlchemy column for sorting."""
    column_map = {
        "name": getattr(model, "name", None) or getattr(model, "filename", None),
        "created_at": model.created_at,
        "updated_at": model.updated_at,
        "size": getattr(model, "size_bytes", model.created_at),
    }
    return column_map.get(sort_by, model.created_at)


async def _count_directory_items(db, directory_id: uuid.UUID) -> int:
    """Count items in a directory."""
    dir_count = (await db.execute(
        select(func.count()).where(
            Directory.parent_id == directory_id,
            Directory.is_deleted == False,
        )
    )).scalar() or 0

    file_count = (await db.execute(
        select(func.count()).where(
            FileMetadata.directory_id == directory_id,
            FileMetadata.is_deleted == False,
        )
    )).scalar() or 0

    return dir_count + file_count
