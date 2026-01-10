"""Pydantic schemas for File operations."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FileResponse(BaseModel):
    """Schema for file metadata response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    library_id: uuid.UUID
    directory_id: Optional[uuid.UUID]
    filename: str
    path: str
    size_bytes: int
    checksum_sha256: str
    content_type: str
    current_version: int
    created_by: uuid.UUID
    modified_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Computed fields
    download_url: Optional[str] = Field(None, description="Presigned download URL")


class FileUpdate(BaseModel):
    """Schema for updating file metadata (rename)."""
    filename: str = Field(..., min_length=1, max_length=255, description="New filename")


class FileMove(BaseModel):
    """Schema for moving a file."""
    directory_id: Optional[uuid.UUID] = Field(
        None,
        description="Target directory ID (null for root level)",
    )


class FileVersionResponse(BaseModel):
    """Schema for file version response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_id: uuid.UUID
    version_number: int
    size_bytes: int
    checksum_sha256: str
    created_by: uuid.UUID
    created_at: datetime
    comment: Optional[str]


# ==========================================================================
# Upload Schemas
# ==========================================================================

class UploadInitRequest(BaseModel):
    """Schema for initiating a file upload."""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream")
    size_bytes: int = Field(..., gt=0, description="Total file size")
    directory_id: Optional[uuid.UUID] = Field(
        None,
        description="Target directory ID (null for root level)",
    )
    on_duplicate: str = Field(
        default="ask",
        description="Action on duplicate: 'ask', 'overwrite', 'rename'",
    )


class UploadInitResponse(BaseModel):
    """Schema for upload initialization response."""
    upload_id: str = Field(..., description="Upload ID for subsequent requests")
    file_id: uuid.UUID = Field(..., description="File ID (for tracking)")
    chunk_size: int = Field(..., description="Recommended chunk size in bytes")
    total_chunks: int = Field(..., description="Expected number of chunks")

    # For presigned upload
    presigned_urls: Optional[List[str]] = Field(
        None,
        description="Presigned URLs for each chunk (if using direct upload)",
    )


class UploadPartRequest(BaseModel):
    """Schema for uploading a file part/chunk."""
    upload_id: str
    part_number: int = Field(..., ge=1, le=10000)
    # Actual data sent as multipart form


class UploadPartResponse(BaseModel):
    """Schema for upload part response."""
    part_number: int
    etag: str
    size_bytes: int


class UploadCompleteRequest(BaseModel):
    """Schema for completing a multipart upload."""
    upload_id: str
    parts: List[UploadPartResponse] = Field(
        ...,
        description="List of uploaded parts with ETags",
    )
    checksum_sha256: Optional[str] = Field(
        None,
        description="Client-calculated checksum for verification",
    )


class UploadCompleteResponse(BaseModel):
    """Schema for upload completion response."""
    file: FileResponse
    version: FileVersionResponse


# ==========================================================================
# Duplicate Handling
# ==========================================================================

class DuplicateConflictResponse(BaseModel):
    """Schema for duplicate file conflict response."""
    conflict: bool = True
    message: str = "A file with this name already exists"
    options: List[str] = ["overwrite", "rename", "cancel"]
    existing_file: FileResponse
    suggested_name: Optional[str] = Field(
        None,
        description="Suggested alternative filename",
    )
