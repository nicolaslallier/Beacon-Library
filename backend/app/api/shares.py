"""API endpoints for share links."""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.schemas.share import (
    GuestAccountCreate,
    GuestAccountResponse,
    ShareAccessRequest,
    ShareAccessResponse,
    ShareLinkCreate,
    ShareLinkPublicResponse,
    ShareLinkResponse,
    ShareLinkUpdate,
    ShareStatistics,
    ShareTargetType,
)
from app.services.share import KeycloakGuestService, ShareService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/shares", tags=["shares"])


def get_share_service(
    db: AsyncSession = Depends(get_db),
) -> ShareService:
    """Get share service dependency."""
    base_url = settings.BASE_URL if hasattr(settings, "BASE_URL") else ""
    return ShareService(db=db, base_url=base_url)


def get_guest_service() -> KeycloakGuestService:
    """Get Keycloak guest service dependency."""
    return KeycloakGuestService(
        keycloak_url=settings.KEYCLOAK_URL,
        realm=settings.KEYCLOAK_REALM,
        client_id=settings.KEYCLOAK_CLIENT_ID,
        client_secret=settings.KEYCLOAK_CLIENT_SECRET,
    )


# =============================================================================
# Authenticated endpoints (require login)
# =============================================================================


@router.post(
    "",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a share link",
    description="Create a new share link for a file, directory, or library.",
)
async def create_share_link(
    data: ShareLinkCreate,
    current_user: dict = Depends(get_current_user),
    service: ShareService = Depends(get_share_service),
):
    """Create a new share link."""
    try:
        share = await service.create_share_link(
            data=data,
            user_id=uuid.UUID(current_user["sub"]),
        )
        return share
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=list[ShareLinkResponse],
    summary="List my share links",
    description="List all share links created by the current user.",
)
async def list_my_shares(
    include_expired: bool = Query(False, description="Include expired shares"),
    current_user: dict = Depends(get_current_user),
    service: ShareService = Depends(get_share_service),
):
    """List all share links created by the current user."""
    return await service.list_user_shares(
        user_id=uuid.UUID(current_user["sub"]),
        include_expired=include_expired,
    )


@router.get(
    "/resource/{target_type}/{target_id}",
    response_model=list[ShareLinkResponse],
    summary="List shares for a resource",
    description="List all share links for a specific file, directory, or library.",
)
async def list_shares_for_resource(
    target_type: ShareTargetType,
    target_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: ShareService = Depends(get_share_service),
):
    """List all share links for a specific resource."""
    return await service.list_shares_for_resource(
        target_type=target_type,
        target_id=target_id,
        user_id=uuid.UUID(current_user["sub"]),
    )


@router.get(
    "/{share_id}",
    response_model=ShareLinkResponse,
    summary="Get share link details",
    description="Get details of a specific share link.",
)
async def get_share_link(
    share_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: ShareService = Depends(get_share_service),
):
    """Get a share link by ID."""
    share = await service.get_share_link(
        share_id=share_id,
        user_id=uuid.UUID(current_user["sub"]),
    )
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )
    return share


@router.patch(
    "/{share_id}",
    response_model=ShareLinkResponse,
    summary="Update share link",
    description="Update a share link's settings.",
)
async def update_share_link(
    share_id: uuid.UUID,
    data: ShareLinkUpdate,
    current_user: dict = Depends(get_current_user),
    service: ShareService = Depends(get_share_service),
):
    """Update a share link."""
    share = await service.update_share_link(
        share_id=share_id,
        data=data,
        user_id=uuid.UUID(current_user["sub"]),
    )
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )
    return share


@router.post(
    "/{share_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke share link",
    description="Revoke (deactivate) a share link without deleting it.",
)
async def revoke_share_link(
    share_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: ShareService = Depends(get_share_service),
):
    """Revoke a share link."""
    success = await service.revoke_share_link(
        share_id=share_id,
        user_id=uuid.UUID(current_user["sub"]),
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )


@router.delete(
    "/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete share link",
    description="Permanently delete a share link.",
)
async def delete_share_link(
    share_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: ShareService = Depends(get_share_service),
):
    """Delete a share link."""
    success = await service.delete_share_link(
        share_id=share_id,
        user_id=uuid.UUID(current_user["sub"]),
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )


@router.get(
    "/{share_id}/statistics",
    response_model=ShareStatistics,
    summary="Get share statistics",
    description="Get access statistics for a share link.",
)
async def get_share_statistics(
    share_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: ShareService = Depends(get_share_service),
):
    """Get statistics for a share link."""
    stats = await service.get_share_statistics(
        share_id=share_id,
        user_id=uuid.UUID(current_user["sub"]),
    )
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )
    return stats


# =============================================================================
# Guest account endpoints (require login)
# =============================================================================


@router.post(
    "/guest",
    response_model=GuestAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create guest account",
    description="Create a guest account in Keycloak for share access.",
)
async def create_guest_account(
    data: GuestAccountCreate,
    current_user: dict = Depends(get_current_user),
    guest_service: KeycloakGuestService = Depends(get_guest_service),
):
    """Create a guest account for share access."""
    try:
        return await guest_service.create_guest_account(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# Public endpoints (no authentication required)
# =============================================================================


@router.get(
    "/public/{token}",
    response_model=ShareLinkPublicResponse,
    summary="Get public share info",
    description="Get public information about a share link (no authentication required).",
)
async def get_public_share_info(
    token: str,
    service: ShareService = Depends(get_share_service),
):
    """Get public information about a share link."""
    share_link = await service.get_share_by_token(token)

    if not share_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or has been revoked",
        )

    # Get target name
    target = await service._get_target(
        ShareTargetType(share_link.target_type),
        share_link.target_id,
    )
    target_name = getattr(target, "name", "Shared Resource")

    import datetime

    is_expired = (
        share_link.expires_at is not None
        and share_link.expires_at < datetime.datetime.now(datetime.timezone.utc)
    )

    return ShareLinkPublicResponse(
        id=share_link.id,
        share_type=share_link.share_type,
        target_type=share_link.target_type,
        target_name=target_name,
        password_protected=share_link.password_hash is not None,
        allow_guest_access=share_link.allow_guest_access,
        is_expired=is_expired,
    )


@router.post(
    "/public/{token}/access",
    response_model=ShareAccessResponse,
    summary="Access shared resource",
    description="Access a shared resource using a share link token.",
)
async def access_share(
    token: str,
    request: Request,
    data: ShareAccessRequest,
    service: ShareService = Depends(get_share_service),
):
    """Access a shared resource."""
    # Get visitor IP
    visitor_ip = request.client.host if request.client else None
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        visitor_ip = forwarded_for.split(",")[0].strip()

    try:
        return await service.access_share(
            token=token,
            request=data,
            visitor_ip=visitor_ip,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
