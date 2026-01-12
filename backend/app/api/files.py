"""API routes for file management."""

import uuid
from datetime import datetime
from typing import Optional, Union

import structlog
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import (
    Cache,
    CurrentUser,
    DbSession,
    FileDep,
    Storage,
)
from app.core.config import settings
from app.models import Directory, FileMetadata, FileVersion, Library
from app.schemas.file import (
    DuplicateConflictResponse,
    FileResponse,
    FileUpdate,
    FileVersionResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
    UploadInitResponse,
    UploadPartResponse,
)
from app.services.search import (
    queue_file_for_deindexing,
    queue_file_for_indexing,
)
from app.services.storage import StorageService

logger = structlog.get_logger(__name__)
router = APIRouter()

# In-memory store for active uploads (in production, use Redis)
_active_uploads: dict = {}


@router.post(
    "/upload/init",
    response_model=Union[UploadInitResponse, DuplicateConflictResponse],
    summary="Initialize file upload",
)
async def init_upload(
    library_id: uuid.UUID = Query(..., description="Target library ID"),
    filename: str = Query(..., min_length=1, max_length=255),
    content_type: str = Query(default="application/octet-stream"),
    # Allow 0-byte files (e.g. empty config stubs like output.tf)
    size_bytes: int = Query(..., ge=0),
    directory_id: Optional[uuid.UUID] = Query(None),
    on_duplicate: str = Query("ask", regex="^(ask|overwrite|rename)$"),
    db: DbSession = None,
    user: CurrentUser = None,
    storage: Storage = None,
    cache: Cache = None,
) -> UploadInitResponse | DuplicateConflictResponse:
    """
    Initialize a file upload.

    For small files (< chunk size), use direct upload.
    For large files, this returns an upload ID for multipart upload.
    """
    # Verify library access
    result = await db.execute(
        select(Library).where(
            Library.id == library_id,
            Library.is_deleted.is_(False),
        )
    )
    library = result.scalar_one_or_none()

    if not library:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found",
        )

    if library.owner_id != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Check file size limit
    max_size = library.max_file_size_bytes or settings.storage_max_file_size
    if size_bytes > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds limit of {max_size} bytes",
        )

    # Get directory path
    dir_path = "/"
    if directory_id:
        result = await db.execute(
            select(Directory).where(
                Directory.id == directory_id,
                Directory.library_id == library_id,
                Directory.is_deleted.is_(False),
            )
        )
        directory = result.scalar_one_or_none()
        if not directory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Directory not found",
            )
        dir_path = directory.full_path

    # Check for existing file
    result = await db.execute(
        select(FileMetadata).where(
            FileMetadata.library_id == library_id,
            FileMetadata.directory_id == directory_id,
            FileMetadata.filename == filename,
            FileMetadata.is_deleted.is_(False),
        )
    )
    existing_file = result.scalar_one_or_none()

    if existing_file:
        if on_duplicate == "ask":
            # Return conflict response
            return DuplicateConflictResponse(
                existing_file=FileResponse(
                    id=existing_file.id,
                    library_id=existing_file.library_id,
                    directory_id=existing_file.directory_id,
                    filename=existing_file.filename,
                    path=existing_file.path,
                    size_bytes=existing_file.size_bytes,
                    checksum_sha256=existing_file.checksum_sha256,
                    content_type=existing_file.content_type,
                    current_version=existing_file.current_version,
                    created_by=existing_file.created_by,
                    modified_by=existing_file.modified_by,
                    created_at=existing_file.created_at,
                    updated_at=existing_file.updated_at,
                ),
                suggested_name=_generate_unique_filename(filename),
            )
        elif on_duplicate == "rename":
            filename = _generate_unique_filename(filename)

    # Create file record
    file_id = uuid.uuid4()
    storage_key = StorageService.generate_storage_key(
        library_id, dir_path, filename, version=1
    )

    # Calculate chunks
    chunk_size = settings.storage_chunk_size
    # For 0-byte files, still treat as a single "chunk".
    if size_bytes == 0:
        total_chunks = 1
    else:
        total_chunks = (size_bytes + chunk_size - 1) // chunk_size

    if total_chunks <= 1:
        # Small file - single upload
        upload_id = str(uuid.uuid4())
        existing_file_id = (
            existing_file.id
            if existing_file and on_duplicate == "overwrite"
            else None
        )
        _active_uploads[upload_id] = {
            "file_id": file_id,
            "library_id": library_id,
            "directory_id": directory_id,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "storage_key": storage_key,
            "bucket": library.bucket_name,
            "user_id": user.user_id,
            "dir_path": dir_path,
            "existing_file_id": existing_file_id,
            "multipart": False,
        }

        return UploadInitResponse(
            upload_id=upload_id,
            file_id=file_id,
            chunk_size=chunk_size,
            total_chunks=1,
        )
    else:
        # Large file - multipart upload
        upload_id = await storage.start_multipart_upload(
            bucket=library.bucket_name,
            key=storage_key,
            content_type=content_type,
        )

        existing_file_id = (
            existing_file.id
            if existing_file and on_duplicate == "overwrite"
            else None
        )
        _active_uploads[upload_id] = {
            "file_id": file_id,
            "library_id": library_id,
            "directory_id": directory_id,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "storage_key": storage_key,
            "bucket": library.bucket_name,
            "user_id": user.user_id,
            "dir_path": dir_path,
            "existing_file_id": existing_file_id,
            "multipart": True,
            "parts": [],
        }

        return UploadInitResponse(
            upload_id=upload_id,
            file_id=file_id,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
        )


@router.post(
    "/upload/part",
    response_model=UploadPartResponse,
    summary="Upload file part",
)
async def upload_part(
    upload_id: str = Query(...),
    part_number: int = Query(..., ge=1, le=10000),
    file: UploadFile = File(...),
    storage: Storage = None,
) -> UploadPartResponse:
    """Upload a single part of a multipart upload."""
    if upload_id not in _active_uploads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or expired",
        )

    upload_info = _active_uploads[upload_id]
    data = await file.read()

    if upload_info["multipart"]:
        part_info = await storage.upload_part(
            bucket=upload_info["bucket"],
            key=upload_info["storage_key"],
            upload_id=upload_id,
            part_number=part_number,
            data=data,
        )

        upload_info["parts"].append(part_info)

        return UploadPartResponse(
            part_number=part_number,
            etag=part_info["ETag"],
            size_bytes=len(data),
        )
    else:
        # Single-part upload - store the data
        upload_info["data"] = data

        return UploadPartResponse(
            part_number=1,
            etag="pending",
            size_bytes=len(data),
        )


@router.post(
    "/upload/complete",
    response_model=UploadCompleteResponse,
    summary="Complete file upload",
)
async def complete_upload(
    data: UploadCompleteRequest,
    db: DbSession,
    storage: Storage,
    cache: Cache,
) -> UploadCompleteResponse:
    """Complete a file upload and create the file record."""
    if data.upload_id not in _active_uploads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or expired",
        )

    upload_info = _active_uploads[data.upload_id]

    try:
        if upload_info["multipart"]:
            # Complete multipart upload
            result = await storage.complete_multipart_upload(
                bucket=upload_info["bucket"],
                key=upload_info["storage_key"],
                upload_id=data.upload_id,
                parts=[{"PartNumber": p.part_number, "ETag": p.etag} for p in data.parts],
            )
            checksum = result.checksum_sha256
            size = result.size_bytes
        else:
            # Single-part upload
            file_data = upload_info.get("data")
            # Note: empty bytes (b"") is valid for 0-byte files.
            if file_data is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No data uploaded",
                )

            result = await storage.upload_file(
                bucket=upload_info["bucket"],
                key=upload_info["storage_key"],
                data=file_data,
                content_type=upload_info["content_type"],
            )
            checksum = result.checksum_sha256
            size = result.size_bytes

        # Verify checksum if provided
        if data.checksum_sha256 and data.checksum_sha256 != checksum:
            logger.warning(
                "checksum_mismatch",
                expected=data.checksum_sha256,
                actual=checksum,
            )

        # Handle overwrite case
        existing_file_id = upload_info.get("existing_file_id")
        if existing_file_id:
            # Update existing file
            result = await db.execute(
                select(FileMetadata).where(FileMetadata.id == existing_file_id)
            )
            file = result.scalar_one()

            # Increment version number for the new content
            new_version_number = file.current_version + 1

            # Update file metadata
            file.size_bytes = size
            file.checksum_sha256 = checksum
            file.storage_key = upload_info["storage_key"]
            file.current_version = new_version_number
            file.modified_by = upload_info["user_id"]

            # Create version record for new content
            version = FileVersion(
                file_id=file.id,
                version_number=new_version_number,
                size_bytes=size,
                checksum_sha256=checksum,
                storage_key=upload_info["storage_key"],
                created_at=datetime.utcnow(),
                created_by=upload_info["user_id"],
            )
            db.add(version)
        else:
            # Create new file
            file = FileMetadata(
                id=upload_info["file_id"],
                library_id=upload_info["library_id"],
                directory_id=upload_info["directory_id"],
                filename=upload_info["filename"],
                path=upload_info["dir_path"],
                size_bytes=size,
                checksum_sha256=checksum,
                content_type=upload_info["content_type"],
                storage_key=upload_info["storage_key"],
                created_by=upload_info["user_id"],
                modified_by=upload_info["user_id"],
            )
            db.add(file)

            # Create initial version
            version = FileVersion(
                file_id=file.id,
                version_number=1,
                size_bytes=size,
                checksum_sha256=checksum,
                storage_key=upload_info["storage_key"],
                created_at=datetime.utcnow(),
                created_by=upload_info["user_id"],
            )
            db.add(version)

        await db.commit()
        await db.refresh(file)

        # Invalidate cache
        await cache.invalidate_file(
            file.id,
            file.library_id,
            file.directory_id,
        )

        logger.info(
            "file_uploaded",
            file_id=str(file.id),
            filename=file.filename,
            size=size,
        )

        # Queue file for semantic search indexing (non-blocking, don't fail upload)
        try:
            await queue_file_for_indexing(file.id, file.library_id)
        except Exception as e:
            logger.warning(
                "search_indexing_queue_failed",
                file_id=str(file.id),
                error=str(e),
            )

        return UploadCompleteResponse(
            file=FileResponse(
                id=file.id,
                library_id=file.library_id,
                directory_id=file.directory_id,
                filename=file.filename,
                path=file.path,
                size_bytes=file.size_bytes,
                checksum_sha256=file.checksum_sha256,
                content_type=file.content_type,
                current_version=file.current_version,
                created_by=file.created_by,
                modified_by=file.modified_by,
                created_at=file.created_at,
                updated_at=file.updated_at,
            ),
            version=FileVersionResponse(
                id=version.id,
                file_id=version.file_id,
                version_number=version.version_number,
                size_bytes=version.size_bytes,
                checksum_sha256=version.checksum_sha256,
                created_by=version.created_by,
                created_at=version.created_at,
                comment=version.comment,
            ),
        )
    finally:
        # Clean up
        del _active_uploads[data.upload_id]


@router.get(
    "/{file_id}",
    response_model=FileResponse,
    summary="Get file metadata",
)
async def get_file(
    file: FileDep,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
) -> FileResponse:
    """Get file metadata."""
    # Verify access
    result = await db.execute(
        select(Library).where(Library.id == file.library_id)
    )
    library = result.scalar_one()

    if library.owner_id != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Generate download URL
    download_url = await storage.generate_presigned_download_url(
        bucket=library.bucket_name,
        key=file.storage_key,
        filename=file.filename,
    )

    return FileResponse(
        id=file.id,
        library_id=file.library_id,
        directory_id=file.directory_id,
        filename=file.filename,
        path=file.path,
        size_bytes=file.size_bytes,
        checksum_sha256=file.checksum_sha256,
        content_type=file.content_type,
        current_version=file.current_version,
        created_by=file.created_by,
        modified_by=file.modified_by,
        created_at=file.created_at,
        updated_at=file.updated_at,
        download_url=download_url,
    )


@router.get(
    "/{file_id}/download",
    summary="Download file",
)
async def download_file(
    file: FileDep,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
):
    """Download file content."""
    # Verify access
    result = await db.execute(
        select(Library).where(Library.id == file.library_id)
    )
    library = result.scalar_one()

    if library.owner_id != user.user_id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    async def stream_file():
        async for chunk in storage.download_file_stream(
            bucket=library.bucket_name,
            key=file.storage_key,
        ):
            yield chunk

    # Encode filename for Content-Disposition header (RFC 5987)
    from urllib.parse import quote

    # Create ASCII-safe fallback (replace non-ASCII with underscores)
    ascii_filename = file.filename.encode(
        'ascii', 'replace'
    ).decode('ascii').replace('?', '_')
    # Create UTF-8 encoded filename for modern browsers
    utf8_filename = quote(file.filename, safe='')

    content_disp = (
        f"attachment; filename=\"{ascii_filename}\"; "
        f"filename*=UTF-8''{utf8_filename}"
    )

    return StreamingResponse(
        stream_file(),
        media_type=file.content_type,
        headers={
            "Content-Disposition": content_disp,
            "Content-Length": str(file.size_bytes),
        },
    )


@router.patch(
    "/{file_id}",
    response_model=FileResponse,
    summary="Rename file",
)
async def rename_file(
    file: FileDep,
    data: FileUpdate,
    db: DbSession,
    user: CurrentUser,
    cache: Cache,
) -> FileResponse:
    """Rename a file."""
    # Check for duplicate
    result = await db.execute(
        select(FileMetadata).where(
            FileMetadata.library_id == file.library_id,
            FileMetadata.directory_id == file.directory_id,
            FileMetadata.filename == data.filename,
            FileMetadata.id != file.id,
            FileMetadata.is_deleted.is_(False),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A file with this name already exists",
        )

    file.filename = data.filename
    file.modified_by = user.user_id

    await db.commit()
    await db.refresh(file)

    await cache.invalidate_file(file.id, file.library_id, file.directory_id)

    return await get_file(file, db, user, None)


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete file",
)
async def delete_file(
    file: FileDep,
    db: DbSession,
    user: CurrentUser,
    cache: Cache,
) -> None:
    """Soft delete a file."""
    file.soft_delete(user.user_id)

    await db.commit()

    await cache.invalidate_file(file.id, file.library_id, file.directory_id)

    logger.info("file_deleted", file_id=str(file.id), filename=file.filename)

    # Best-effort: keep vector DB in sync (don't fail delete if it errors)
    try:
        await queue_file_for_deindexing(file.id, file.library_id)
    except Exception as e:
        logger.warning(
            "search_deindex_queue_failed",
            file_id=str(file.id),
            error=str(e),
        )


def _generate_unique_filename(filename: str) -> str:
    """Generate a unique filename by adding a suffix."""
    import time

    if "." in filename:
        name, ext = filename.rsplit(".", 1)
        return f"{name}_{int(time.time())}.{ext}"
    return f"{filename}_{int(time.time())}"
