"""Pydantic schemas for Directory operations."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DirectoryBase(BaseModel):
    """Base schema for directory data."""
    name: str = Field(..., min_length=1, max_length=255, description="Directory name")


class DirectoryCreate(DirectoryBase):
    """Schema for creating a new directory."""
    parent_id: Optional[uuid.UUID] = Field(
        None,
        description="Parent directory ID (null for root level)",
    )


class DirectoryUpdate(BaseModel):
    """Schema for updating a directory (rename)."""
    name: str = Field(..., min_length=1, max_length=255, description="New directory name")


class DirectoryMove(BaseModel):
    """Schema for moving a directory."""
    new_parent_id: Optional[uuid.UUID] = Field(
        None,
        description="New parent directory ID (null for root level)",
    )


class DirectoryResponse(DirectoryBase):
    """Schema for directory response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    library_id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    path: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Computed fields
    item_count: int = Field(default=0, description="Number of items in directory")
