"""Security utilities for Keycloak authentication and authorization."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set

import httpx
import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.config import settings

logger = structlog.get_logger(__name__)

# HTTP Bearer scheme for token extraction
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class UserContext:
    """
    Authenticated user context extracted from JWT token.

    Contains user identity and authorization information.
    """
    user_id: uuid.UUID
    username: str
    email: Optional[str]
    name: Optional[str]
    roles: Set[str]
    groups: Set[str]
    token: str
    token_exp: datetime
    is_guest: bool = False

    # Request context
    correlation_id: uuid.UUID = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the specified roles."""
        return bool(self.roles & set(roles))

    def has_all_roles(self, roles: List[str]) -> bool:
        """Check if user has all specified roles."""
        return set(roles) <= self.roles

    @property
    def is_admin(self) -> bool:
        """Check if user is a library admin."""
        return "library-admin" in self.roles

    @property
    def is_user(self) -> bool:
        """Check if user is a regular library user."""
        return "library-user" in self.roles or self.is_admin


class KeycloakJWKS:
    """
    Keycloak JWKS (JSON Web Key Set) manager.

    Fetches and caches public keys for JWT verification.
    """

    def __init__(self):
        self._keys: Dict[str, Any] = {}
        self._last_fetch: Optional[datetime] = None
        self._cache_ttl = 3600  # 1 hour

    async def get_public_key(self, kid: str) -> Optional[Dict[str, Any]]:
        """
        Get a public key by key ID.

        Args:
            kid: Key ID from JWT header

        Returns:
            JWK dict or None if not found
        """
        # Refresh if cache is stale or key not found
        if self._should_refresh() or kid not in self._keys:
            await self._fetch_keys()

        return self._keys.get(kid)

    def _should_refresh(self) -> bool:
        """Check if keys should be refreshed."""
        if self._last_fetch is None:
            return True
        elapsed = (datetime.utcnow() - self._last_fetch).total_seconds()
        return elapsed > self._cache_ttl

    async def _fetch_keys(self) -> None:
        """Fetch JWKS from Keycloak."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    settings.keycloak_jwks_url,
                    timeout=10.0,
                )
                response.raise_for_status()
                jwks = response.json()

                self._keys = {
                    key["kid"]: key
                    for key in jwks.get("keys", [])
                }
                self._last_fetch = datetime.utcnow()
                logger.debug("jwks_fetched", key_count=len(self._keys))

        except Exception as e:
            logger.error("jwks_fetch_failed", error=str(e))
            # Keep existing keys on error
            if not self._keys:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service unavailable",
                )


# Singleton JWKS manager
_jwks_manager: Optional[KeycloakJWKS] = None


def get_jwks_manager() -> KeycloakJWKS:
    """Get the JWKS manager singleton."""
    global _jwks_manager
    if _jwks_manager is None:
        _jwks_manager = KeycloakJWKS()
    return _jwks_manager


async def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Decode header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing key ID",
            )

        # Get public key
        jwks = get_jwks_manager()
        key = await jwks.get_public_key(kid)

        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: unknown key ID",
            )

        # Verify and decode
        audience = settings.keycloak_audience or settings.keycloak_client_id

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=settings.keycloak_issuer,
            options={
                "verify_signature": settings.keycloak_verify_token,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
            },
        )

        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except JWTError as e:
        logger.warning("jwt_decode_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def extract_user_context(
    payload: Dict[str, Any],
    token: str,
    request: Request,
) -> UserContext:
    """
    Extract user context from decoded JWT payload.

    Args:
        payload: Decoded JWT payload
        token: Original token string
        request: FastAPI request object

    Returns:
        UserContext with user information
    """
    # Extract user ID (Keycloak uses 'sub')
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: invalid subject format",
        )

    # Extract roles from realm_access and resource_access
    roles: Set[str] = set()

    # Realm roles
    realm_access = payload.get("realm_access", {})
    roles.update(realm_access.get("roles", []))

    # Client-specific roles
    resource_access = payload.get("resource_access", {})
    client_access = resource_access.get(settings.keycloak_client_id, {})
    roles.update(client_access.get("roles", []))

    # Extract groups
    groups: Set[str] = set(payload.get("groups", []))

    # Token expiry
    exp_timestamp = payload.get("exp", 0)
    token_exp = datetime.utcfromtimestamp(exp_timestamp)

    # Check if guest account
    is_guest = "guest" in roles or payload.get("azp") == settings.keycloak_guest_client_id

    # Generate correlation ID
    correlation_id = uuid.uuid4()

    # Extract client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return UserContext(
        user_id=user_id,
        username=payload.get("preferred_username", ""),
        email=payload.get("email"),
        name=payload.get("name"),
        roles=roles,
        groups=groups,
        token=token,
        token_exp=token_exp,
        is_guest=is_guest,
        correlation_id=correlation_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserContext:
    """
    FastAPI dependency to get the current authenticated user.

    Usage:
        @app.get("/protected")
        async def protected_route(user: UserContext = Depends(get_current_user)):
            ...
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = await decode_token(token)
    user = extract_user_context(payload, token, request)

    logger.debug(
        "user_authenticated",
        user_id=str(user.user_id),
        username=user.username,
        roles=list(user.roles),
    )

    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[UserContext]:
    """
    FastAPI dependency to optionally get the current user.

    Returns None if no valid authentication is provided.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


def require_roles(*required_roles: str):
    """
    Dependency factory to require specific roles.

    Usage:
        @app.get("/admin")
        async def admin_route(user: UserContext = Depends(require_roles("library-admin"))):
            ...
    """
    async def role_checker(user: UserContext = Depends(get_current_user)) -> UserContext:
        if not user.has_any_role(list(required_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(required_roles)}",
            )
        return user

    return role_checker


def require_admin():
    """Dependency to require admin role."""
    return require_roles("library-admin")


def require_user():
    """Dependency to require user role (admin or regular user)."""
    return require_roles("library-admin", "library-user")
