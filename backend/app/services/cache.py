"""Redis caching service for file and directory metadata."""

import json
import uuid
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

import redis.asyncio as redis
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CacheService:
    """
    Redis-based caching service for file and directory metadata.

    Provides:
    - Key-value caching with TTL
    - Cache invalidation
    - Namespace-based key organization
    - JSON serialization for complex objects
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._prefix = settings.cache_prefix
        self._default_ttl = settings.cache_ttl_seconds

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            logger.info("redis_connected", url=settings.redis_url)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("redis_disconnected")

    @property
    def client(self) -> redis.Redis:
        """Get the Redis client."""
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client

    # ==========================================================================
    # Key Management
    # ==========================================================================

    def _make_key(self, namespace: str, *parts: str) -> str:
        """
        Build a cache key with prefix and namespace.

        Format: {prefix}{namespace}:{part1}:{part2}:...
        """
        key_parts = [self._prefix, namespace] + list(parts)
        return ":".join(str(p) for p in key_parts)

    # ==========================================================================
    # Basic Operations
    # ==========================================================================

    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache."""
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.warning("cache_get_error", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to store
            ttl: Time-to-live in seconds (default from settings)

        Returns:
            True if successful
        """
        try:
            if ttl is None:
                ttl = self._default_ttl
            await self.client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.warning("cache_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Redis pattern (e.g., "beacon:library:*")

        Returns:
            Number of keys deleted
        """
        try:
            keys = []
            async for key in self.client.scan_iter(pattern):
                keys.append(key)

            if keys:
                await self.client.delete(*keys)

            logger.debug("cache_pattern_deleted", pattern=pattern, count=len(keys))
            return len(keys)
        except Exception as e:
            logger.warning("cache_delete_pattern_error", pattern=pattern, error=str(e))
            return 0

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.warning("cache_exists_error", key=key, error=str(e))
            return False

    # ==========================================================================
    # JSON Operations
    # ==========================================================================

    async def get_json(self, key: str) -> Optional[Any]:
        """Get and deserialize a JSON value."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning("cache_json_decode_error", key=key)
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Serialize and set a JSON value."""
        try:
            json_value = json.dumps(value, default=str)
            return await self.set(key, json_value, ttl)
        except (TypeError, ValueError) as e:
            logger.warning("cache_json_encode_error", key=key, error=str(e))
            return False

    # ==========================================================================
    # Library Cache Operations
    # ==========================================================================

    def library_key(self, library_id: uuid.UUID) -> str:
        """Get cache key for a library."""
        return self._make_key("library", str(library_id))

    def library_list_key(self, user_id: uuid.UUID) -> str:
        """Get cache key for a user's library list."""
        return self._make_key("library_list", str(user_id))

    async def get_library(self, library_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get cached library data."""
        return await self.get_json(self.library_key(library_id))

    async def set_library(
        self,
        library_id: uuid.UUID,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache library data."""
        return await self.set_json(self.library_key(library_id), data, ttl)

    async def invalidate_library(self, library_id: uuid.UUID) -> None:
        """Invalidate library cache."""
        await self.delete(self.library_key(library_id))
        # Also invalidate any library lists that might contain this library
        await self.delete_pattern(f"{self._prefix}library_list:*")

    # ==========================================================================
    # Directory Cache Operations
    # ==========================================================================

    def directory_key(self, directory_id: uuid.UUID) -> str:
        """Get cache key for a directory."""
        return self._make_key("directory", str(directory_id))

    def directory_listing_key(self, library_id: uuid.UUID, path: str) -> str:
        """Get cache key for directory listing."""
        # Hash the path to avoid key length issues
        path_hash = hash(path) & 0xFFFFFFFF
        return self._make_key("dir_listing", str(library_id), str(path_hash))

    async def get_directory(self, directory_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get cached directory data."""
        return await self.get_json(self.directory_key(directory_id))

    async def set_directory(
        self,
        directory_id: uuid.UUID,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache directory data."""
        return await self.set_json(self.directory_key(directory_id), data, ttl)

    async def get_directory_listing(
        self,
        library_id: uuid.UUID,
        path: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached directory listing."""
        return await self.get_json(self.directory_listing_key(library_id, path))

    async def set_directory_listing(
        self,
        library_id: uuid.UUID,
        path: str,
        data: List[Dict[str, Any]],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache directory listing."""
        return await self.set_json(
            self.directory_listing_key(library_id, path),
            data,
            ttl,
        )

    async def invalidate_directory(
        self,
        directory_id: uuid.UUID,
        library_id: uuid.UUID,
    ) -> None:
        """Invalidate directory and related caches."""
        await self.delete(self.directory_key(directory_id))
        # Invalidate all directory listings for the library
        await self.delete_pattern(
            f"{self._prefix}dir_listing:{library_id}:*"
        )

    # ==========================================================================
    # File Cache Operations
    # ==========================================================================

    def file_key(self, file_id: uuid.UUID) -> str:
        """Get cache key for a file."""
        return self._make_key("file", str(file_id))

    def file_versions_key(self, file_id: uuid.UUID) -> str:
        """Get cache key for file versions."""
        return self._make_key("file_versions", str(file_id))

    async def get_file(self, file_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get cached file metadata."""
        return await self.get_json(self.file_key(file_id))

    async def set_file(
        self,
        file_id: uuid.UUID,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache file metadata."""
        return await self.set_json(self.file_key(file_id), data, ttl)

    async def invalidate_file(
        self,
        file_id: uuid.UUID,
        library_id: uuid.UUID,
        directory_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Invalidate file and related caches."""
        await self.delete(self.file_key(file_id))
        await self.delete(self.file_versions_key(file_id))
        # Invalidate directory listings
        await self.delete_pattern(
            f"{self._prefix}dir_listing:{library_id}:*"
        )

    # ==========================================================================
    # Bulk Operations
    # ==========================================================================

    async def invalidate_library_cache(self, library_id: uuid.UUID) -> int:
        """
        Invalidate all cache entries for a library.

        This is useful when a library is deleted or major changes occur.
        """
        pattern = f"{self._prefix}*:{library_id}*"
        count = await self.delete_pattern(pattern)
        await self.invalidate_library(library_id)
        return count

    async def flush_all(self) -> None:
        """
        Flush all cache entries.

        WARNING: This clears the entire cache. Use with caution.
        """
        await self.delete_pattern(f"{self._prefix}*")
        logger.warning("cache_flushed")


# Singleton instance
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Get the cache service singleton."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()
    return _cache_service


async def close_cache_service() -> None:
    """Close the cache service connection."""
    global _cache_service
    if _cache_service:
        await _cache_service.disconnect()
        _cache_service = None


def cached(
    key_func: Callable[..., str],
    ttl: Optional[int] = None,
):
    """
    Decorator for caching function results.

    Args:
        key_func: Function to generate cache key from arguments
        ttl: Cache TTL in seconds

    Usage:
        @cached(lambda library_id: f"library:{library_id}")
        async def get_library(library_id: uuid.UUID) -> Library:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            cache = await get_cache_service()
            key = key_func(*args, **kwargs)

            # Try cache first
            cached_value = await cache.get_json(key)
            if cached_value is not None:
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                await cache.set_json(key, result, ttl)

            return result

        return wrapper
    return decorator
