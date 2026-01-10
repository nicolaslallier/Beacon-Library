"""API dependencies for injection."""

import uuid
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import UserContext, get_current_user, require_roles
from app.models import Library, Directory, FileMetadata
from app.services.cache import CacheService, get_cache_service
from app.services.storage import StorageService, get_storage_service

# Type aliases for cleaner dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserContext, Depends(get_current_user)]
AdminUser = Annotated[UserContext, Depends(require_roles("library-admin"))]
Storage = Annotated[StorageService, Depends(get_storage_service)]


async def get_cache() -> CacheService:
    """Dependency to get cache service."""
    return await get_cache_service()


Cache = Annotated[CacheService, Depends(get_cache)]


# ==========================================================================
# Resource Dependencies
# ==========================================================================

async def get_library_or_404(
    library_id: Annotated[uuid.UUID, Path(description="Library ID")],
    db: DbSession,
    user: CurrentUser,
) -> Library:
    """
    Get a library by ID or raise 404.

    Also checks that the library is not deleted and user has access.
    """
    result = await db.execute(
        select(Library).where(
            Library.id == library_id,
            Library.is_deleted == False,
        )
    )
    library = result.scalar_one_or_none()

    if not library:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found",
        )

    # Check access (owner or admin)
    if library.owner_id != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this library",
        )

    return library


LibraryDep = Annotated[Library, Depends(get_library_or_404)]


async def get_directory_or_404(
    directory_id: Annotated[uuid.UUID, Path(description="Directory ID")],
    db: DbSession,
) -> Directory:
    """Get a directory by ID or raise 404."""
    result = await db.execute(
        select(Directory).where(
            Directory.id == directory_id,
            Directory.is_deleted == False,
        )
    )
    directory = result.scalar_one_or_none()

    if not directory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directory not found",
        )

    return directory


DirectoryDep = Annotated[Directory, Depends(get_directory_or_404)]


async def get_file_or_404(
    file_id: Annotated[uuid.UUID, Path(description="File ID")],
    db: DbSession,
) -> FileMetadata:
    """Get a file by ID or raise 404."""
    result = await db.execute(
        select(FileMetadata).where(
            FileMetadata.id == file_id,
            FileMetadata.is_deleted == False,
        )
    )
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return file


FileDep = Annotated[FileMetadata, Depends(get_file_or_404)]


# ==========================================================================
# Pagination Dependencies
# ==========================================================================

class PaginationParams:
    """Common pagination parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


Pagination = Annotated[PaginationParams, Depends()]


class SortParams:
    """Common sorting parameters."""

    def __init__(
        self,
        sort_by: str = Query("name", description="Field to sort by"),
        sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    ):
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.is_descending = sort_order == "desc"


Sort = Annotated[SortParams, Depends()]
