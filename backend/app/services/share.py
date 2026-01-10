"""Share link service for managing file/directory/library sharing."""

import datetime
import hashlib
import secrets
import uuid
from typing import Optional

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.directory import Directory
from app.models.file import FileMetadata
from app.models.library import Library
from app.models.share import ShareLink
from app.schemas.share import (
    GuestAccountCreate,
    GuestAccountResponse,
    ShareAccessRequest,
    ShareAccessResponse,
    ShareLinkCreate,
    ShareLinkResponse,
    ShareLinkUpdate,
    ShareStatistics,
    ShareTargetType,
    ShareType,
)

logger = structlog.get_logger(__name__)


class ShareService:
    """Service for managing share links."""

    def __init__(self, db: AsyncSession, base_url: str = ""):
        self.db = db
        self.base_url = base_url

    async def create_share_link(
        self,
        data: ShareLinkCreate,
        user_id: uuid.UUID,
    ) -> ShareLinkResponse:
        """Create a new share link for a file, directory, or library."""
        # Verify target exists and user has access
        target = await self._get_target(data.target_type, data.target_id)
        if not target:
            raise ValueError(f"{data.target_type.value} not found")

        # Generate unique token
        token = secrets.token_urlsafe(32)

        # Hash password if provided
        password_hash = None
        if data.password_protected and data.password:
            password_hash = self._hash_password(data.password)

        # Create share link
        share_link = ShareLink(
            token=token,
            share_type=data.share_type.value,
            target_type=data.target_type.value,
            target_id=data.target_id,
            created_by=user_id,
            password_hash=password_hash,
            expires_at=data.expires_at,
            max_access_count=data.max_access_count,
            allow_guest_access=data.allow_guest_access,
            notify_on_access=data.notify_on_access,
        )

        self.db.add(share_link)

        # Log audit event
        audit_event = AuditEvent(
            event_type="share_created",
            resource_type=data.target_type.value,
            resource_id=data.target_id,
            user_id=user_id,
            details={
                "share_type": data.share_type.value,
                "expires_at": data.expires_at.isoformat() if data.expires_at else None,
                "max_access_count": data.max_access_count,
            },
        )
        self.db.add(audit_event)

        await self.db.commit()
        await self.db.refresh(share_link)

        logger.info(
            "share_link_created",
            share_id=str(share_link.id),
            target_type=data.target_type.value,
            target_id=str(data.target_id),
            user_id=str(user_id),
        )

        return self._to_response(share_link)

    async def get_share_link(
        self,
        share_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[ShareLinkResponse]:
        """Get a share link by ID."""
        query = select(ShareLink).where(
            and_(
                ShareLink.id == share_id,
                ShareLink.is_deleted == False,
            )
        )

        if user_id:
            query = query.where(ShareLink.created_by == user_id)

        result = await self.db.execute(query)
        share_link = result.scalar_one_or_none()

        if not share_link:
            return None

        return self._to_response(share_link)

    async def get_share_by_token(self, token: str) -> Optional[ShareLink]:
        """Get a share link by its token."""
        query = select(ShareLink).where(
            and_(
                ShareLink.token == token,
                ShareLink.is_deleted == False,
                ShareLink.is_active == True,
            )
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_shares_for_resource(
        self,
        target_type: ShareTargetType,
        target_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[ShareLinkResponse]:
        """List all share links for a specific resource."""
        query = select(ShareLink).where(
            and_(
                ShareLink.target_type == target_type.value,
                ShareLink.target_id == target_id,
                ShareLink.created_by == user_id,
                ShareLink.is_deleted == False,
            )
        ).order_by(ShareLink.created_at.desc())

        result = await self.db.execute(query)
        shares = result.scalars().all()

        return [self._to_response(share) for share in shares]

    async def list_user_shares(
        self,
        user_id: uuid.UUID,
        include_expired: bool = False,
    ) -> list[ShareLinkResponse]:
        """List all share links created by a user."""
        conditions = [
            ShareLink.created_by == user_id,
            ShareLink.is_deleted == False,
        ]

        if not include_expired:
            conditions.append(
                (ShareLink.expires_at == None) |
                (ShareLink.expires_at > datetime.datetime.now(datetime.timezone.utc))
            )

        query = select(ShareLink).where(and_(*conditions)).order_by(
            ShareLink.created_at.desc()
        )

        result = await self.db.execute(query)
        shares = result.scalars().all()

        return [self._to_response(share) for share in shares]

    async def update_share_link(
        self,
        share_id: uuid.UUID,
        data: ShareLinkUpdate,
        user_id: uuid.UUID,
    ) -> Optional[ShareLinkResponse]:
        """Update a share link."""
        query = select(ShareLink).where(
            and_(
                ShareLink.id == share_id,
                ShareLink.created_by == user_id,
                ShareLink.is_deleted == False,
            )
        )

        result = await self.db.execute(query)
        share_link = result.scalar_one_or_none()

        if not share_link:
            return None

        # Update fields
        update_data = data.model_dump(exclude_unset=True)

        if "password" in update_data:
            password = update_data.pop("password")
            if password:
                share_link.password_hash = self._hash_password(password)

        for field, value in update_data.items():
            if hasattr(share_link, field):
                setattr(share_link, field, value)

        # Log audit event
        audit_event = AuditEvent(
            event_type="share_updated",
            resource_type=share_link.target_type,
            resource_id=share_link.target_id,
            user_id=user_id,
            details={"updated_fields": list(update_data.keys())},
        )
        self.db.add(audit_event)

        await self.db.commit()
        await self.db.refresh(share_link)

        logger.info(
            "share_link_updated",
            share_id=str(share_id),
            user_id=str(user_id),
        )

        return self._to_response(share_link)

    async def revoke_share_link(
        self,
        share_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Revoke (deactivate) a share link."""
        query = select(ShareLink).where(
            and_(
                ShareLink.id == share_id,
                ShareLink.created_by == user_id,
                ShareLink.is_deleted == False,
            )
        )

        result = await self.db.execute(query)
        share_link = result.scalar_one_or_none()

        if not share_link:
            return False

        share_link.is_active = False

        # Log audit event
        audit_event = AuditEvent(
            event_type="share_revoked",
            resource_type=share_link.target_type,
            resource_id=share_link.target_id,
            user_id=user_id,
            details={"share_id": str(share_id)},
        )
        self.db.add(audit_event)

        await self.db.commit()

        logger.info(
            "share_link_revoked",
            share_id=str(share_id),
            user_id=str(user_id),
        )

        return True

    async def delete_share_link(
        self,
        share_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Soft delete a share link."""
        query = select(ShareLink).where(
            and_(
                ShareLink.id == share_id,
                ShareLink.created_by == user_id,
                ShareLink.is_deleted == False,
            )
        )

        result = await self.db.execute(query)
        share_link = result.scalar_one_or_none()

        if not share_link:
            return False

        share_link.is_deleted = True
        share_link.is_active = False

        # Log audit event
        audit_event = AuditEvent(
            event_type="share_deleted",
            resource_type=share_link.target_type,
            resource_id=share_link.target_id,
            user_id=user_id,
            details={"share_id": str(share_id)},
        )
        self.db.add(audit_event)

        await self.db.commit()

        logger.info(
            "share_link_deleted",
            share_id=str(share_id),
            user_id=str(user_id),
        )

        return True

    async def access_share(
        self,
        token: str,
        request: ShareAccessRequest,
        visitor_ip: Optional[str] = None,
    ) -> ShareAccessResponse:
        """Access a shared resource via share link."""
        share_link = await self.get_share_by_token(token)

        if not share_link:
            raise ValueError("Share link not found or has been revoked")

        # Check if expired
        if share_link.expires_at and share_link.expires_at < datetime.datetime.now(
            datetime.timezone.utc
        ):
            raise ValueError("Share link has expired")

        # Check access count limit
        if (
            share_link.max_access_count
            and share_link.access_count >= share_link.max_access_count
        ):
            raise ValueError("Share link access limit reached")

        # Verify password if required
        if share_link.password_hash:
            if not request.password:
                raise ValueError("Password required")
            if not self._verify_password(request.password, share_link.password_hash):
                raise ValueError("Invalid password")

        # Get target name
        target = await self._get_target(
            ShareTargetType(share_link.target_type),
            share_link.target_id,
        )
        target_name = getattr(target, "name", "Unknown")

        # Increment access count
        share_link.access_count += 1
        share_link.last_accessed_at = datetime.datetime.now(datetime.timezone.utc)

        # Log access event
        audit_event = AuditEvent(
            event_type="share_accessed",
            resource_type=share_link.target_type,
            resource_id=share_link.target_id,
            user_id=share_link.created_by,  # Owner gets notified
            details={
                "share_id": str(share_link.id),
                "visitor_ip": visitor_ip,
                "access_count": share_link.access_count,
            },
        )
        self.db.add(audit_event)

        await self.db.commit()

        # Generate temporary access token
        access_token = secrets.token_urlsafe(48)

        # Token expires in 1 hour for view, 24 hours for download/edit
        token_lifetime = (
            datetime.timedelta(hours=24)
            if share_link.share_type in ["download", "edit"]
            else datetime.timedelta(hours=1)
        )

        logger.info(
            "share_link_accessed",
            share_id=str(share_link.id),
            access_count=share_link.access_count,
            visitor_ip=visitor_ip,
        )

        return ShareAccessResponse(
            access_token=access_token,
            share_type=ShareType(share_link.share_type),
            target_type=ShareTargetType(share_link.target_type),
            target_id=share_link.target_id,
            target_name=target_name,
            expires_at=datetime.datetime.now(datetime.timezone.utc) + token_lifetime,
        )

    async def get_share_statistics(
        self,
        share_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[ShareStatistics]:
        """Get access statistics for a share link."""
        query = select(ShareLink).where(
            and_(
                ShareLink.id == share_id,
                ShareLink.created_by == user_id,
                ShareLink.is_deleted == False,
            )
        )

        result = await self.db.execute(query)
        share_link = result.scalar_one_or_none()

        if not share_link:
            return None

        # Get access events for this share
        events_query = select(AuditEvent).where(
            and_(
                AuditEvent.event_type == "share_accessed",
                AuditEvent.resource_id == share_link.target_id,
            )
        ).order_by(AuditEvent.created_at.desc())

        events_result = await self.db.execute(events_query)
        events = events_result.scalars().all()

        # Calculate statistics
        access_by_date: dict[str, int] = {}
        unique_ips: set[str] = set()

        for event in events:
            date_key = event.created_at.strftime("%Y-%m-%d")
            access_by_date[date_key] = access_by_date.get(date_key, 0) + 1

            if event.details and "visitor_ip" in event.details:
                unique_ips.add(event.details["visitor_ip"])

        return ShareStatistics(
            share_id=share_id,
            total_accesses=share_link.access_count,
            unique_visitors=len(unique_ips),
            last_accessed_at=share_link.last_accessed_at,
            access_by_date=access_by_date,
        )

    async def _get_target(
        self,
        target_type: ShareTargetType,
        target_id: uuid.UUID,
    ):
        """Get the target resource (file, directory, or library)."""
        if target_type == ShareTargetType.FILE:
            query = select(FileMetadata).where(
                and_(
                    FileMetadata.id == target_id,
                    FileMetadata.is_deleted == False,
                )
            )
        elif target_type == ShareTargetType.DIRECTORY:
            query = select(Directory).where(
                and_(
                    Directory.id == target_id,
                    Directory.is_deleted == False,
                )
            )
        elif target_type == ShareTargetType.LIBRARY:
            query = select(Library).where(
                and_(
                    Library.id == target_id,
                    Library.is_deleted == False,
                )
            )
        else:
            return None

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt."""
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}:{hashed}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, hashed = password_hash.split(":")
            return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == hashed
        except ValueError:
            return False

    def _to_response(self, share_link: ShareLink) -> ShareLinkResponse:
        """Convert a ShareLink model to a response schema."""
        now = datetime.datetime.now(datetime.timezone.utc)

        is_expired = (
            share_link.expires_at is not None
            and share_link.expires_at < now
        )

        remaining_accesses = None
        if share_link.max_access_count:
            remaining_accesses = max(
                0, share_link.max_access_count - share_link.access_count
            )

        return ShareLinkResponse(
            id=share_link.id,
            token=share_link.token,
            share_type=ShareType(share_link.share_type),
            target_type=ShareTargetType(share_link.target_type),
            target_id=share_link.target_id,
            created_by=share_link.created_by,
            password_protected=share_link.password_hash is not None,
            expires_at=share_link.expires_at,
            max_access_count=share_link.max_access_count,
            allow_guest_access=share_link.allow_guest_access,
            notify_on_access=share_link.notify_on_access,
            access_count=share_link.access_count,
            is_active=share_link.is_active,
            created_at=share_link.created_at,
            updated_at=share_link.updated_at,
            share_url=f"{self.base_url}/share/{share_link.token}" if self.base_url else None,
            is_expired=is_expired,
            remaining_accesses=remaining_accesses,
        )


class KeycloakGuestService:
    """Service for managing Keycloak guest accounts."""

    def __init__(
        self,
        keycloak_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
    ):
        self.keycloak_url = keycloak_url
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret

    async def create_guest_account(
        self,
        data: GuestAccountCreate,
    ) -> GuestAccountResponse:
        """Create a guest account in Keycloak for share access."""
        import httpx

        # Get admin token
        admin_token = await self._get_admin_token()

        # Generate temporary password
        temp_password = secrets.token_urlsafe(12)

        # Create user in Keycloak
        user_data = {
            "username": f"guest_{data.email.replace('@', '_at_').replace('.', '_')}",
            "email": data.email,
            "enabled": True,
            "emailVerified": False,
            "credentials": [
                {
                    "type": "password",
                    "value": temp_password,
                    "temporary": True,
                }
            ],
            "attributes": {
                "share_link_id": [str(data.share_link_id)],
                "account_type": ["guest"],
            },
            "groups": ["/guests"],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.keycloak_url}/admin/realms/{self.realm}/users",
                json=user_data,
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            if response.status_code == 409:
                # User already exists
                raise ValueError("Guest account already exists for this email")

            response.raise_for_status()

            # Get user ID from location header
            location = response.headers.get("Location", "")
            guest_id = location.split("/")[-1] if location else ""

        login_url = (
            f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/auth"
            f"?client_id={self.client_id}&response_type=code&scope=openid"
        )

        logger.info(
            "guest_account_created",
            email=data.email,
            share_link_id=str(data.share_link_id),
        )

        return GuestAccountResponse(
            guest_id=guest_id,
            email=data.email,
            temporary_password=temp_password,
            login_url=login_url,
        )

    async def delete_guest_account(self, guest_id: str) -> bool:
        """Delete a guest account from Keycloak."""
        import httpx

        admin_token = await self._get_admin_token()

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.keycloak_url}/admin/realms/{self.realm}/users/{guest_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            if response.status_code == 404:
                return False

            response.raise_for_status()

        logger.info("guest_account_deleted", guest_id=guest_id)
        return True

    async def _get_admin_token(self) -> str:
        """Get an admin token for Keycloak API calls."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]
