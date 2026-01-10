"""Trash service for managing soft-deleted items."""

import datetime
import uuid
from typing import Optional

import structlog
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit import ActorType, AuditAction
from app.models.directory import Directory
from app.models.file import FileMetadata
from app.models.library import Library
from app.schemas.trash import (
    EmptyTrashResponse,
    RestoreRequest,
    RestoreResponse,
    TrashItemResponse,
    TrashItemType,
    TrashListResponse,
)
from app.services.audit import AuditService
from app.services.storage import MinIOService

logger = structlog.get_logger(__name__)


class TrashService:
    """Service for managing trash/recycle bin operations."""

    def __init__(
        self,
        db: AsyncSession,
        storage: Optional[MinIOService] = None,
        audit: Optional[AuditService] = None,
    ):
        self.db = db
        self.storage = storage
        self.audit = audit
        self.retention_days = settings.trash_retention_days

    async def get_trash_items(
        self,
        library_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TrashListResponse:
        """Get all items in trash."""
        items: list[TrashItemResponse] = []
        total_size = 0

        # Query deleted files
        file_conditions = [FileMetadata.is_deleted == True]
        if library_id:
            file_conditions.append(FileMetadata.library_id == library_id)

        files_query = (
            select(FileMetadata)
            .where(and_(*file_conditions))
            .order_by(FileMetadata.updated_at.desc())
        )

        files_result = await self.db.execute(files_query)
        deleted_files = files_result.scalars().all()

        for file in deleted_files:
            expires_at = file.updated_at + datetime.timedelta(days=self.retention_days)
            days_remaining = (expires_at - datetime.datetime.now(datetime.timezone.utc)).days

            items.append(TrashItemResponse(
                item_type=TrashItemType.FILE,
                item_id=file.id,
                name=file.name,
                original_path=file.path or f"/{file.name}",
                library_id=file.library_id,
                deleted_by=file.updated_by or uuid.uuid4(),  # Fallback
                deleted_at=file.updated_at,
                expires_at=expires_at,
                size_bytes=file.size,
                days_until_permanent=max(0, days_remaining),
                can_restore=days_remaining > 0,
            ))
            total_size += file.size or 0

        # Query deleted directories
        dir_conditions = [Directory.is_deleted == True]
        if library_id:
            dir_conditions.append(Directory.library_id == library_id)

        dirs_query = (
            select(Directory)
            .where(and_(*dir_conditions))
            .order_by(Directory.updated_at.desc())
        )

        dirs_result = await self.db.execute(dirs_query)
        deleted_dirs = dirs_result.scalars().all()

        for dir in deleted_dirs:
            expires_at = dir.updated_at + datetime.timedelta(days=self.retention_days)
            days_remaining = (expires_at - datetime.datetime.now(datetime.timezone.utc)).days

            items.append(TrashItemResponse(
                item_type=TrashItemType.DIRECTORY,
                item_id=dir.id,
                name=dir.name,
                original_path=dir.path or f"/{dir.name}",
                library_id=dir.library_id,
                deleted_by=dir.updated_by or uuid.uuid4(),
                deleted_at=dir.updated_at,
                expires_at=expires_at,
                size_bytes=None,
                days_until_permanent=max(0, days_remaining),
                can_restore=days_remaining > 0,
            ))

        # Sort by deleted_at descending
        items.sort(key=lambda x: x.deleted_at, reverse=True)

        # Apply pagination
        paginated_items = items[offset:offset + limit]

        return TrashListResponse(
            items=paginated_items,
            total=len(items),
            total_size_bytes=total_size,
        )

    async def restore_item(
        self,
        request: RestoreRequest,
        user_id: uuid.UUID,
    ) -> RestoreResponse:
        """Restore an item from trash."""
        if request.item_type == TrashItemType.FILE:
            return await self._restore_file(request, user_id)
        elif request.item_type == TrashItemType.DIRECTORY:
            return await self._restore_directory(request, user_id)
        else:
            raise ValueError(f"Cannot restore item type: {request.item_type}")

    async def _restore_file(
        self,
        request: RestoreRequest,
        user_id: uuid.UUID,
    ) -> RestoreResponse:
        """Restore a file from trash."""
        query = select(FileMetadata).where(
            and_(
                FileMetadata.id == request.item_id,
                FileMetadata.is_deleted == True,
            )
        )

        result = await self.db.execute(query)
        file = result.scalar_one_or_none()

        if not file:
            raise ValueError("File not found in trash")

        # Check expiry
        expires_at = file.updated_at + datetime.timedelta(days=self.retention_days)
        if datetime.datetime.now(datetime.timezone.utc) > expires_at:
            raise ValueError("File has expired and cannot be restored")

        # Determine restore location
        if request.restore_to_original and file.directory_id:
            # Check if original directory still exists
            dir_query = select(Directory).where(
                and_(
                    Directory.id == file.directory_id,
                    Directory.is_deleted == False,
                )
            )
            dir_result = await self.db.execute(dir_query)
            original_dir = dir_result.scalar_one_or_none()

            if not original_dir:
                # Original directory was deleted, restore to library root
                file.directory_id = None
        elif request.new_parent_id:
            file.directory_id = request.new_parent_id
        else:
            file.directory_id = None

        # Restore the file
        file.is_deleted = False
        file.updated_by = user_id
        file.updated_at = datetime.datetime.now(datetime.timezone.utc)

        await self.db.commit()

        # Log audit event
        if self.audit:
            await self.audit.log_user_action(
                action=AuditAction.FILE_RESTORE,
                user_id=user_id,
                user_name=None,
                target_type="file",
                target_id=file.id,
                target_name=file.name,
                library_id=file.library_id,
                details={"restored_from_trash": True},
            )

        logger.info(
            "file_restored",
            file_id=str(file.id),
            user_id=str(user_id),
        )

        return RestoreResponse(
            item_type=TrashItemType.FILE,
            item_id=file.id,
            restored_path=file.path or f"/{file.name}",
            message=f"File '{file.name}' has been restored",
        )

    async def _restore_directory(
        self,
        request: RestoreRequest,
        user_id: uuid.UUID,
    ) -> RestoreResponse:
        """Restore a directory from trash."""
        query = select(Directory).where(
            and_(
                Directory.id == request.item_id,
                Directory.is_deleted == True,
            )
        )

        result = await self.db.execute(query)
        directory = result.scalar_one_or_none()

        if not directory:
            raise ValueError("Directory not found in trash")

        # Check expiry
        expires_at = directory.updated_at + datetime.timedelta(days=self.retention_days)
        if datetime.datetime.now(datetime.timezone.utc) > expires_at:
            raise ValueError("Directory has expired and cannot be restored")

        # Determine restore location
        if request.restore_to_original and directory.parent_id:
            # Check if parent directory still exists
            parent_query = select(Directory).where(
                and_(
                    Directory.id == directory.parent_id,
                    Directory.is_deleted == False,
                )
            )
            parent_result = await self.db.execute(parent_query)
            original_parent = parent_result.scalar_one_or_none()

            if not original_parent:
                directory.parent_id = None
        elif request.new_parent_id:
            directory.parent_id = request.new_parent_id
        else:
            directory.parent_id = None

        # Restore the directory
        directory.is_deleted = False
        directory.updated_by = user_id
        directory.updated_at = datetime.datetime.now(datetime.timezone.utc)

        # Also restore all children (files and subdirectories)
        await self._restore_directory_children(directory.id, user_id)

        await self.db.commit()

        # Log audit event
        if self.audit:
            await self.audit.log_user_action(
                action=AuditAction.DIRECTORY_RESTORE,
                user_id=user_id,
                user_name=None,
                target_type="directory",
                target_id=directory.id,
                target_name=directory.name,
                library_id=directory.library_id,
                details={"restored_from_trash": True},
            )

        logger.info(
            "directory_restored",
            directory_id=str(directory.id),
            user_id=str(user_id),
        )

        return RestoreResponse(
            item_type=TrashItemType.DIRECTORY,
            item_id=directory.id,
            restored_path=directory.path or f"/{directory.name}",
            message=f"Directory '{directory.name}' and its contents have been restored",
        )

    async def _restore_directory_children(
        self,
        directory_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Recursively restore all children of a directory."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # Restore child files
        await self.db.execute(
            update(FileMetadata)
            .where(
                and_(
                    FileMetadata.directory_id == directory_id,
                    FileMetadata.is_deleted == True,
                )
            )
            .values(
                is_deleted=False,
                updated_by=user_id,
                updated_at=now,
            )
        )

        # Get child directories
        child_dirs_query = select(Directory).where(
            and_(
                Directory.parent_id == directory_id,
                Directory.is_deleted == True,
            )
        )

        result = await self.db.execute(child_dirs_query)
        child_dirs = result.scalars().all()

        for child_dir in child_dirs:
            child_dir.is_deleted = False
            child_dir.updated_by = user_id
            child_dir.updated_at = now

            # Recursively restore grandchildren
            await self._restore_directory_children(child_dir.id, user_id)

    async def permanent_delete(
        self,
        item_type: TrashItemType,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Permanently delete an item from trash."""
        if item_type == TrashItemType.FILE:
            return await self._permanent_delete_file(item_id, user_id)
        elif item_type == TrashItemType.DIRECTORY:
            return await self._permanent_delete_directory(item_id, user_id)
        return False

    async def _permanent_delete_file(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Permanently delete a file."""
        query = select(FileMetadata).where(
            and_(
                FileMetadata.id == file_id,
                FileMetadata.is_deleted == True,
            )
        )

        result = await self.db.execute(query)
        file = result.scalar_one_or_none()

        if not file:
            return False

        # Delete from storage
        if self.storage and file.storage_key:
            try:
                await self.storage.delete_file(
                    bucket_name=f"beacon-lib-{file.library_id}",
                    object_name=file.storage_key,
                )
            except Exception as e:
                logger.warning(
                    "storage_delete_failed",
                    file_id=str(file_id),
                    error=str(e),
                )

        # Delete from database
        await self.db.delete(file)
        await self.db.commit()

        logger.info(
            "file_permanently_deleted",
            file_id=str(file_id),
            user_id=str(user_id),
        )

        return True

    async def _permanent_delete_directory(
        self,
        directory_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Permanently delete a directory and all its contents."""
        query = select(Directory).where(
            and_(
                Directory.id == directory_id,
                Directory.is_deleted == True,
            )
        )

        result = await self.db.execute(query)
        directory = result.scalar_one_or_none()

        if not directory:
            return False

        # Recursively delete children first
        await self._permanent_delete_directory_children(directory_id, user_id)

        # Delete the directory itself
        await self.db.delete(directory)
        await self.db.commit()

        logger.info(
            "directory_permanently_deleted",
            directory_id=str(directory_id),
            user_id=str(user_id),
        )

        return True

    async def _permanent_delete_directory_children(
        self,
        directory_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Recursively delete all children of a directory."""
        # Delete child files
        files_query = select(FileMetadata).where(
            FileMetadata.directory_id == directory_id
        )
        files_result = await self.db.execute(files_query)
        files = files_result.scalars().all()

        for file in files:
            await self._permanent_delete_file(file.id, user_id)

        # Delete child directories
        dirs_query = select(Directory).where(
            Directory.parent_id == directory_id
        )
        dirs_result = await self.db.execute(dirs_query)
        child_dirs = dirs_result.scalars().all()

        for child_dir in child_dirs:
            await self._permanent_delete_directory_children(child_dir.id, user_id)
            await self.db.delete(child_dir)

    async def empty_trash(
        self,
        library_id: Optional[uuid.UUID],
        user_id: uuid.UUID,
    ) -> EmptyTrashResponse:
        """Empty all items from trash."""
        deleted_count = 0
        freed_bytes = 0

        # Get all deleted files
        file_conditions = [FileMetadata.is_deleted == True]
        if library_id:
            file_conditions.append(FileMetadata.library_id == library_id)

        files_query = select(FileMetadata).where(and_(*file_conditions))
        files_result = await self.db.execute(files_query)
        files = files_result.scalars().all()

        for file in files:
            freed_bytes += file.size or 0
            await self._permanent_delete_file(file.id, user_id)
            deleted_count += 1

        # Get all deleted directories
        dir_conditions = [Directory.is_deleted == True]
        if library_id:
            dir_conditions.append(Directory.library_id == library_id)

        dirs_query = select(Directory).where(and_(*dir_conditions))
        dirs_result = await self.db.execute(dirs_query)
        directories = dirs_result.scalars().all()

        for directory in directories:
            await self._permanent_delete_directory(directory.id, user_id)
            deleted_count += 1

        logger.info(
            "trash_emptied",
            user_id=str(user_id),
            library_id=str(library_id) if library_id else "all",
            deleted_count=deleted_count,
            freed_bytes=freed_bytes,
        )

        return EmptyTrashResponse(
            deleted_count=deleted_count,
            freed_bytes=freed_bytes,
        )

    async def cleanup_expired(self) -> int:
        """Clean up items that have exceeded the retention period.

        This should be called by a scheduled task.
        """
        cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=self.retention_days
        )

        deleted_count = 0

        # Find expired files
        files_query = select(FileMetadata).where(
            and_(
                FileMetadata.is_deleted == True,
                FileMetadata.updated_at < cutoff_date,
            )
        )

        files_result = await self.db.execute(files_query)
        expired_files = files_result.scalars().all()

        for file in expired_files:
            await self._permanent_delete_file(file.id, uuid.uuid4())  # System user
            deleted_count += 1

        # Find expired directories
        dirs_query = select(Directory).where(
            and_(
                Directory.is_deleted == True,
                Directory.updated_at < cutoff_date,
            )
        )

        dirs_result = await self.db.execute(dirs_query)
        expired_dirs = dirs_result.scalars().all()

        for directory in expired_dirs:
            await self._permanent_delete_directory(directory.id, uuid.uuid4())
            deleted_count += 1

        logger.info(
            "expired_trash_cleaned",
            deleted_count=deleted_count,
            cutoff_date=cutoff_date.isoformat(),
        )

        return deleted_count
