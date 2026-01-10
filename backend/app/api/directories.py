"""API routes for directory management."""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import select

from app.api.deps import (
    Cache,
    CurrentUser,
    DbSession,
    LibraryDep,
)
from app.models import Directory
from app.schemas.directory import (
    DirectoryCreate,
    DirectoryMove,
    DirectoryResponse,
    DirectoryUpdate,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def normalize_path(path: str) -> str:
    """Normalize a directory path."""
    # Remove leading/trailing slashes and normalize
    parts = [p for p in path.split("/") if p]
    return "/" + "/".join(parts) if parts else "/"


@router.post(
    "",
    response_model=DirectoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new directory",
)
async def create_directory(
    library_id: uuid.UUID,
    data: DirectoryCreate,
    library: LibraryDep,
    db: DbSession,
    user: CurrentUser,
    cache: Cache,
) -> DirectoryResponse:
    """Create a new directory in the library."""
    # Validate parent if provided
    parent_path = "/"
    if data.parent_id:
        result = await db.execute(
            select(Directory).where(
                Directory.id == data.parent_id,
                Directory.library_id == library_id,
                Directory.is_deleted == False,
            )
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent directory not found",
            )
        parent_path = parent.full_path

    # Check for duplicate name
    result = await db.execute(
        select(Directory).where(
            Directory.library_id == library_id,
            Directory.parent_id == data.parent_id,
            Directory.name == data.name,
            Directory.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A directory with this name already exists",
        )

    # Create directory
    directory = Directory(
        library_id=library_id,
        parent_id=data.parent_id,
        name=data.name,
        path=parent_path,
        created_by=user.user_id,
    )

    db.add(directory)
    await db.commit()
    await db.refresh(directory)

    # Invalidate cache
    await cache.invalidate_directory(directory.id, library_id)

    logger.info(
        "directory_created",
        directory_id=str(directory.id),
        library_id=str(library_id),
        name=data.name,
        path=directory.full_path,
    )

    return DirectoryResponse(
        id=directory.id,
        library_id=directory.library_id,
        parent_id=directory.parent_id,
        name=directory.name,
        path=directory.full_path,
        created_by=directory.created_by,
        created_at=directory.created_at,
        updated_at=directory.updated_at,
        item_count=0,
    )


@router.get(
    "/{directory_id}",
    response_model=DirectoryResponse,
    summary="Get directory details",
)
async def get_directory(
    library_id: uuid.UUID,
    directory_id: uuid.UUID,
    library: LibraryDep,
    db: DbSession,
) -> DirectoryResponse:
    """Get details of a specific directory."""
    result = await db.execute(
        select(Directory).where(
            Directory.id == directory_id,
            Directory.library_id == library_id,
            Directory.is_deleted == False,
        )
    )
    directory = result.scalar_one_or_none()

    if not directory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directory not found",
        )

    # Count items
    from sqlalchemy import func
    from app.models import FileMetadata

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

    return DirectoryResponse(
        id=directory.id,
        library_id=directory.library_id,
        parent_id=directory.parent_id,
        name=directory.name,
        path=directory.full_path,
        created_by=directory.created_by,
        created_at=directory.created_at,
        updated_at=directory.updated_at,
        item_count=dir_count + file_count,
    )


@router.patch(
    "/{directory_id}",
    response_model=DirectoryResponse,
    summary="Rename directory",
)
async def rename_directory(
    library_id: uuid.UUID,
    directory_id: uuid.UUID,
    data: DirectoryUpdate,
    library: LibraryDep,
    db: DbSession,
    user: CurrentUser,
    cache: Cache,
) -> DirectoryResponse:
    """Rename a directory."""
    result = await db.execute(
        select(Directory).where(
            Directory.id == directory_id,
            Directory.library_id == library_id,
            Directory.is_deleted == False,
        )
    )
    directory = result.scalar_one_or_none()

    if not directory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directory not found",
        )

    # Check for duplicate name in same parent
    result = await db.execute(
        select(Directory).where(
            Directory.library_id == library_id,
            Directory.parent_id == directory.parent_id,
            Directory.name == data.name,
            Directory.id != directory_id,
            Directory.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A directory with this name already exists",
        )

    old_name = directory.name
    directory.name = data.name

    # Update paths of all descendants
    await _update_descendant_paths(db, directory)

    await db.commit()
    await db.refresh(directory)

    # Invalidate cache
    await cache.invalidate_directory(directory.id, library_id)

    logger.info(
        "directory_renamed",
        directory_id=str(directory_id),
        old_name=old_name,
        new_name=data.name,
    )

    return await get_directory(library_id, directory_id, library, db)


@router.post(
    "/{directory_id}/move",
    response_model=DirectoryResponse,
    summary="Move directory",
)
async def move_directory(
    library_id: uuid.UUID,
    directory_id: uuid.UUID,
    data: DirectoryMove,
    library: LibraryDep,
    db: DbSession,
    user: CurrentUser,
    cache: Cache,
) -> DirectoryResponse:
    """Move a directory to a new parent."""
    result = await db.execute(
        select(Directory).where(
            Directory.id == directory_id,
            Directory.library_id == library_id,
            Directory.is_deleted == False,
        )
    )
    directory = result.scalar_one_or_none()

    if not directory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directory not found",
        )

    # Validate new parent
    new_parent_path = "/"
    if data.new_parent_id:
        # Can't move to self
        if data.new_parent_id == directory_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot move directory into itself",
            )

        result = await db.execute(
            select(Directory).where(
                Directory.id == data.new_parent_id,
                Directory.library_id == library_id,
                Directory.is_deleted == False,
            )
        )
        new_parent = result.scalar_one_or_none()

        if not new_parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target directory not found",
            )

        # Can't move to a descendant
        if new_parent.path.startswith(directory.full_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot move directory into its own subdirectory",
            )

        new_parent_path = new_parent.full_path

    # Check for duplicate name in new parent
    result = await db.execute(
        select(Directory).where(
            Directory.library_id == library_id,
            Directory.parent_id == data.new_parent_id,
            Directory.name == directory.name,
            Directory.id != directory_id,
            Directory.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A directory with this name already exists in the target location",
        )

    # Update parent and path
    old_path = directory.full_path
    directory.parent_id = data.new_parent_id
    directory.path = new_parent_path

    # Update paths of all descendants
    await _update_descendant_paths(db, directory)

    await db.commit()
    await db.refresh(directory)

    # Invalidate cache
    await cache.invalidate_directory(directory.id, library_id)

    logger.info(
        "directory_moved",
        directory_id=str(directory_id),
        old_path=old_path,
        new_path=directory.full_path,
    )

    return await get_directory(library_id, directory_id, library, db)


@router.delete(
    "/{directory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete directory",
)
async def delete_directory(
    library_id: uuid.UUID,
    directory_id: uuid.UUID,
    library: LibraryDep,
    db: DbSession,
    user: CurrentUser,
    cache: Cache,
) -> None:
    """
    Soft delete a directory and all its contents.
    """
    result = await db.execute(
        select(Directory).where(
            Directory.id == directory_id,
            Directory.library_id == library_id,
            Directory.is_deleted == False,
        )
    )
    directory = result.scalar_one_or_none()

    if not directory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directory not found",
        )

    # Soft delete the directory and all descendants
    await _soft_delete_recursive(db, directory, user.user_id)

    await db.commit()

    # Invalidate cache
    await cache.invalidate_directory(directory.id, library_id)

    logger.info(
        "directory_deleted",
        directory_id=str(directory_id),
        path=directory.full_path,
    )


async def _update_descendant_paths(db: DbSession, directory: Directory) -> None:
    """Update paths of all descendant directories and files."""
    from app.models import FileMetadata

    new_base_path = directory.full_path

    # Update child directories recursively
    result = await db.execute(
        select(Directory).where(
            Directory.parent_id == directory.id,
            Directory.is_deleted == False,
        )
    )
    children = result.scalars().all()

    for child in children:
        child.path = new_base_path
        await _update_descendant_paths(db, child)

    # Update files in this directory
    result = await db.execute(
        select(FileMetadata).where(
            FileMetadata.directory_id == directory.id,
            FileMetadata.is_deleted == False,
        )
    )
    files = result.scalars().all()

    for file in files:
        file.path = new_base_path


async def _soft_delete_recursive(
    db: DbSession,
    directory: Directory,
    user_id: uuid.UUID,
) -> None:
    """Recursively soft delete a directory and its contents."""
    from app.models import FileMetadata

    # Soft delete child directories
    result = await db.execute(
        select(Directory).where(
            Directory.parent_id == directory.id,
            Directory.is_deleted == False,
        )
    )
    children = result.scalars().all()

    for child in children:
        await _soft_delete_recursive(db, child, user_id)

    # Soft delete files
    result = await db.execute(
        select(FileMetadata).where(
            FileMetadata.directory_id == directory.id,
            FileMetadata.is_deleted == False,
        )
    )
    files = result.scalars().all()

    for file in files:
        file.soft_delete(user_id)

    # Soft delete the directory itself
    directory.soft_delete(user_id)
