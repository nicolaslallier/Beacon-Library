"""Pydantic schemas for trash/recycle bin operations."""

import datetime
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TrashItemType(str, Enum):
    """Type of item in trash."""

    FILE = "file"
    DIRECTORY = "directory"
    LIBRARY = "library"


class TrashItemBase(BaseModel):
    """Base schema for trash items."""

    item_type: TrashItemType
    item_id: uuid.UUID
    name: str
    original_path: str
    library_id: uuid.UUID
    deleted_by: uuid.UUID
    deleted_at: datetime.datetime
    expires_at: datetime.datetime
    size_bytes: Optional[int] = None


class TrashItemResponse(TrashItemBase):
    """Response schema for trash items."""

    model_config = ConfigDict(from_attributes=True)

    days_until_permanent: int
    can_restore: bool = True


class TrashListResponse(BaseModel):
    """Response for listing trash items."""

    items: list[TrashItemResponse]
    total: int
    total_size_bytes: int


class RestoreRequest(BaseModel):
    """Request to restore an item from trash."""

    item_type: TrashItemType
    item_id: uuid.UUID
    restore_to_original: bool = Field(
        default=True,
        description="Restore to original location or library root",
    )
    new_parent_id: Optional[uuid.UUID] = Field(
        default=None,
        description="New parent directory ID (if not restoring to original)",
    )


class RestoreResponse(BaseModel):
    """Response after restoring an item."""

    item_type: TrashItemType
    item_id: uuid.UUID
    restored_path: str
    message: str


class PermanentDeleteRequest(BaseModel):
    """Request to permanently delete items."""

    item_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="List of item IDs to permanently delete",
    )


class EmptyTrashResponse(BaseModel):
    """Response after emptying trash."""

    deleted_count: int
    freed_bytes: int
