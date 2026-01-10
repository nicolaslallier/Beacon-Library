"""Pydantic schemas for share links."""

import datetime
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ShareType(str, Enum):
    """Type of share link."""

    VIEW = "view"
    DOWNLOAD = "download"
    EDIT = "edit"


class ShareTargetType(str, Enum):
    """Type of resource being shared."""

    FILE = "file"
    DIRECTORY = "directory"
    LIBRARY = "library"


class ShareLinkBase(BaseModel):
    """Base schema for share links."""

    share_type: ShareType = Field(
        default=ShareType.VIEW,
        description="Permission level for the share link"
    )
    password_protected: bool = Field(
        default=False,
        description="Whether the share link requires a password"
    )
    expires_at: Optional[datetime.datetime] = Field(
        default=None,
        description="Expiration date/time for the share link"
    )
    max_access_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of times the link can be accessed"
    )
    allow_guest_access: bool = Field(
        default=True,
        description="Whether unauthenticated users can access the share"
    )
    notify_on_access: bool = Field(
        default=False,
        description="Notify owner when the link is accessed"
    )


class ShareLinkCreate(ShareLinkBase):
    """Schema for creating a share link."""

    target_type: ShareTargetType = Field(
        ...,
        description="Type of resource being shared"
    )
    target_id: uuid.UUID = Field(
        ...,
        description="ID of the resource being shared"
    )
    password: Optional[str] = Field(
        default=None,
        min_length=4,
        description="Password for accessing the share (if password_protected)"
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure password is provided if password_protected is True."""
        if info.data.get("password_protected") and not v:
            raise ValueError("Password is required when password_protected is True")
        return v


class ShareLinkUpdate(BaseModel):
    """Schema for updating a share link."""

    share_type: Optional[ShareType] = None
    password_protected: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=4)
    expires_at: Optional[datetime.datetime] = None
    max_access_count: Optional[int] = Field(default=None, ge=1)
    allow_guest_access: Optional[bool] = None
    notify_on_access: Optional[bool] = None
    is_active: Optional[bool] = None


class ShareLinkResponse(ShareLinkBase):
    """Schema for share link responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    token: str
    target_type: ShareTargetType
    target_id: uuid.UUID
    created_by: uuid.UUID
    access_count: int
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    # Computed fields
    share_url: Optional[str] = None
    is_expired: bool = False
    remaining_accesses: Optional[int] = None


class ShareLinkPublicResponse(BaseModel):
    """Public response for accessing a share link (no sensitive data)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    share_type: ShareType
    target_type: ShareTargetType
    target_name: str
    password_protected: bool
    allow_guest_access: bool
    is_expired: bool = False


class ShareAccessRequest(BaseModel):
    """Request to access a share link."""

    password: Optional[str] = Field(
        default=None,
        description="Password if the share is password protected"
    )


class ShareAccessResponse(BaseModel):
    """Response after successfully accessing a share link."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(
        ...,
        description="Temporary access token for the shared resource"
    )
    share_type: ShareType
    target_type: ShareTargetType
    target_id: uuid.UUID
    target_name: str
    expires_at: datetime.datetime


class GuestAccountCreate(BaseModel):
    """Schema for creating a guest account via Keycloak."""

    email: str = Field(
        ...,
        description="Guest email address"
    )
    share_link_id: uuid.UUID = Field(
        ...,
        description="ID of the share link to associate with the guest"
    )


class GuestAccountResponse(BaseModel):
    """Response for guest account creation."""

    guest_id: str = Field(
        ...,
        description="Keycloak user ID for the guest"
    )
    email: str
    temporary_password: Optional[str] = Field(
        default=None,
        description="Temporary password (only returned on creation)"
    )
    login_url: str


class ShareStatistics(BaseModel):
    """Statistics for a share link."""

    share_id: uuid.UUID
    total_accesses: int
    unique_visitors: int
    last_accessed_at: Optional[datetime.datetime] = None
    access_by_date: dict[str, int] = Field(
        default_factory=dict,
        description="Access count grouped by date"
    )
