"""Pydantic schemas for browsing/listing operations."""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ItemType(str, Enum):
    """Type of browse item."""
    DIRECTORY = "directory"
    FILE = "file"


class BrowseItem(BaseModel):
    """Schema for a single item in browse results."""
    id: uuid.UUID
    name: str
    type: ItemType
    path: str

    # Common fields
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID

    # File-specific fields (null for directories)
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None
    checksum_sha256: Optional[str] = None
    current_version: Optional[int] = None

    # Directory-specific fields (null for files)
    item_count: Optional[int] = None


class BrowseResponse(BaseModel):
    """Schema for browse/listing response."""
    library_id: uuid.UUID
    path: str
    parent_id: Optional[uuid.UUID] = Field(
        None,
        description="Parent directory ID (null if at root)",
    )

    # Breadcrumb for navigation
    breadcrumb: List[dict] = Field(
        default_factory=list,
        description="Path components for breadcrumb navigation",
    )

    # Items in current directory
    items: List[BrowseItem]

    # Pagination
    total: int
    page: int
    page_size: int
    has_more: bool

    # Sorting
    sort_by: str = "name"
    sort_order: str = "asc"


class SearchRequest(BaseModel):
    """Schema for search request."""
    query: str = Field(..., min_length=1, max_length=500)
    library_id: Optional[uuid.UUID] = None
    content_type: Optional[str] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


class SearchResponse(BaseModel):
    """Schema for search response."""
    query: str
    items: List[BrowseItem]
    total: int
    page: int
    page_size: int
    has_more: bool
