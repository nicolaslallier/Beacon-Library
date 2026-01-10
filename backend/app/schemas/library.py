"""Pydantic schemas for Library operations."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LibraryBase(BaseModel):
    """Base schema for library data."""
    name: str = Field(..., min_length=1, max_length=255, description="Library name")
    description: Optional[str] = Field(None, max_length=2000, description="Library description")


class LibraryCreate(LibraryBase):
    """Schema for creating a new library."""
    mcp_write_enabled: bool = Field(
        default=False,
        description="Enable MCP write operations for AI agents",
    )
    max_file_size_bytes: Optional[int] = Field(
        None,
        gt=0,
        description="Maximum file size in bytes (null for default)",
    )


class LibraryUpdate(BaseModel):
    """Schema for updating a library."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    mcp_write_enabled: Optional[bool] = None
    max_file_size_bytes: Optional[int] = Field(None, gt=0)


class LibraryResponse(LibraryBase):
    """Schema for library response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bucket_name: str
    owner_id: uuid.UUID
    created_by: uuid.UUID
    mcp_write_enabled: bool
    max_file_size_bytes: Optional[int]
    created_at: datetime
    updated_at: datetime

    # Computed fields
    file_count: int = Field(default=0, description="Number of files in library")
    total_size_bytes: int = Field(default=0, description="Total size of all files")


class LibraryListResponse(BaseModel):
    """Schema for paginated library list."""
    items: List[LibraryResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
