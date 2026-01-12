"""Access control service for MCP Vector Server."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = structlog.get_logger(__name__)


class RateLimitConfig:
    """Rate limit configuration for MCP agents."""

    def __init__(
        self,
        requests_per_minute: int = 100,
        window_seconds: int = 60,
    ):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds


class RateLimiter:
    """Simple in-memory rate limiter for MCP agents."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig(
            requests_per_minute=settings.mcp_rate_limit_requests,
            window_seconds=settings.mcp_rate_limit_window,
        )
        self._requests: Dict[str, List[datetime]] = {}

    def is_allowed(self, agent_id: str) -> bool:
        """Check if an agent is allowed to make a request."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.config.window_seconds)

        # Clean old requests
        if agent_id in self._requests:
            self._requests[agent_id] = [
                ts for ts in self._requests[agent_id] if ts > window_start
            ]
        else:
            self._requests[agent_id] = []

        # Check limit
        if len(self._requests[agent_id]) >= self.config.requests_per_minute:
            return False

        # Record request
        self._requests[agent_id].append(now)
        return True

    def get_remaining(self, agent_id: str) -> int:
        """Get remaining requests for an agent."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.config.window_seconds)

        if agent_id not in self._requests:
            return self.config.requests_per_minute

        recent = [ts for ts in self._requests[agent_id] if ts > window_start]
        return max(0, self.config.requests_per_minute - len(recent))


class LibraryPolicy:
    """Policy configuration for library access."""

    def __init__(
        self,
        library_id: uuid.UUID,
        read_enabled: bool = True,
        write_enabled: bool = False,
        allowed_agents: Optional[List[str]] = None,
    ):
        self.library_id = library_id
        self.read_enabled = read_enabled
        self.write_enabled = write_enabled
        self.allowed_agents = allowed_agents  # None means all agents allowed

    def can_read(self, agent_id: str) -> bool:
        """Check if agent can read from library."""
        if not self.read_enabled:
            return False
        if self.allowed_agents is not None and agent_id not in self.allowed_agents:
            return False
        return True

    def can_write(self, agent_id: str) -> bool:
        """Check if agent can write to library."""
        if not self.write_enabled:
            return False
        if self.allowed_agents is not None and agent_id not in self.allowed_agents:
            return False
        return True


class AccessControlService:
    """Service for managing access control to libraries."""

    def __init__(self):
        self._library_policies: Dict[uuid.UUID, LibraryPolicy] = {}
        self.rate_limiter = RateLimiter()
        self._engine = None
        self._session_factory = None

    async def initialize(self):
        """Initialize database connection."""
        if self._engine is None:
            self._engine = create_async_engine(
                settings.database_url,
                echo=False,
                pool_pre_ping=True,
            )
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

    async def close(self):
        """Close database connection."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("AccessControlService not initialized")
        return self._session_factory()

    def set_library_policy(self, policy: LibraryPolicy):
        """Set access policy for a library."""
        self._library_policies[policy.library_id] = policy

    def get_library_policy(self, library_id: uuid.UUID) -> LibraryPolicy:
        """Get access policy for a library."""
        if library_id in self._library_policies:
            return self._library_policies[library_id]

        # Default policy: read-only
        return LibraryPolicy(
            library_id=library_id,
            read_enabled=True,
            write_enabled=settings.mcp_default_write_enabled,
        )

    def check_rate_limit(self, agent_id: str) -> bool:
        """Check if agent is within rate limits."""
        return self.rate_limiter.is_allowed(agent_id)

    def get_rate_limit_remaining(self, agent_id: str) -> int:
        """Get remaining rate limit for agent."""
        return self.rate_limiter.get_remaining(agent_id)

    async def get_accessible_libraries(
        self,
        agent_id: str,
        for_write: bool = False,
    ) -> List[uuid.UUID]:
        """Get list of library IDs accessible to the agent.

        Args:
            agent_id: The agent making the request
            for_write: If True, only return libraries with write access

        Returns:
            List of accessible library UUIDs
        """
        await self.initialize()

        async with self.get_session() as session:
            try:
                # Query all non-deleted libraries from the database
                # Note: We don't import the model to avoid circular dependencies
                # Instead, we use raw SQL
                from sqlalchemy import text

                result = await session.execute(
                    text("""
                        SELECT id, mcp_write_enabled
                        FROM libraries
                        WHERE is_deleted = false
                    """)
                )
                libraries = result.fetchall()

                accessible = []
                for lib_id, mcp_write_enabled in libraries:
                    lib_uuid = uuid.UUID(str(lib_id))
                    policy = self.get_library_policy(lib_uuid)

                    if for_write:
                        # Check both policy and DB flag
                        if policy.can_write(agent_id) and mcp_write_enabled:
                            accessible.append(lib_uuid)
                    else:
                        if policy.can_read(agent_id):
                            accessible.append(lib_uuid)

                return accessible

            except Exception as e:
                logger.error(
                    "get_accessible_libraries_error",
                    agent_id=agent_id,
                    error=str(e),
                )
                return []

    async def check_library_access(
        self,
        library_id: uuid.UUID,
        agent_id: str,
        for_write: bool = False,
    ) -> bool:
        """Check if agent has access to a specific library.

        Args:
            library_id: The library to check
            agent_id: The agent making the request
            for_write: If True, check write access

        Returns:
            True if access is allowed
        """
        policy = self.get_library_policy(library_id)

        if for_write:
            if not policy.can_write(agent_id):
                return False

            # Also check DB flag for write access
            await self.initialize()
            async with self.get_session() as session:
                try:
                    from sqlalchemy import text

                    result = await session.execute(
                        text("""
                            SELECT mcp_write_enabled
                            FROM libraries
                            WHERE id = :library_id AND is_deleted = false
                        """),
                        {"library_id": str(library_id)},
                    )
                    row = result.fetchone()
                    if not row:
                        return False
                    return row[0]  # mcp_write_enabled

                except Exception as e:
                    logger.error(
                        "check_library_write_error",
                        library_id=str(library_id),
                        error=str(e),
                    )
                    return False
        else:
            return policy.can_read(agent_id)

    async def library_exists(self, library_id: uuid.UUID) -> bool:
        """Check if a library exists."""
        await self.initialize()

        async with self.get_session() as session:
            try:
                from sqlalchemy import text

                result = await session.execute(
                    text("""
                        SELECT 1
                        FROM libraries
                        WHERE id = :library_id AND is_deleted = false
                    """),
                    {"library_id": str(library_id)},
                )
                return result.fetchone() is not None

            except Exception as e:
                logger.error(
                    "library_exists_error",
                    library_id=str(library_id),
                    error=str(e),
                )
                return False
