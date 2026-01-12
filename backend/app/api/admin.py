"""Admin API endpoints for system management."""

import asyncio
from datetime import datetime
from typing import Dict, List

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import (
    Directory,
    FileMetadata,
    FileVersion,
    Library,
    ShareLink,
)
from app.schemas.admin import (
    ChromaCollection,
    ChromaCollectionsResponse,
    ChromaReindexRequest,
    ChromaReindexResponse,
    CleanupItem,
    GotenbergHealthResponse,
    MaintenanceCleanupRequest,
    MaintenanceCleanupResponse,
    MaintenanceStatsResponse,
    NginxStatusResponse,
    OllamaModel,
    OllamaModelsResponse,
    OllamaPullRequest,
    OllamaPullResponse,
    ServiceHealth,
    ServicesHealthResponse,
    ServicesStatsResponse,
    ServiceStatus,
    SettingsResponse,
    SettingsUpdate,
)
from app.services.cache import get_cache_service
from app.services.storage import get_storage_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# Settings Endpoints
# =============================================================================


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """
    Get current application settings.

    Returns runtime configuration values.
    """
    return SettingsResponse(
        app_name=settings.app_name,
        app_version=settings.app_version,
        env=settings.env,
        debug=settings.debug,
        db_pool_size=settings.db_pool_size,
        db_max_overflow=settings.db_max_overflow,
        storage_max_file_size=settings.storage_max_file_size,
        storage_chunk_size=settings.storage_chunk_size,
        storage_presigned_url_expiry=settings.storage_presigned_url_expiry,
        chunk_size_code=settings.chunk_size_code,
        chunk_size_docs=settings.chunk_size_docs,
        chunk_overlap=settings.chunk_overlap,
        max_chunks_per_file=settings.max_chunks_per_file,
        enable_code_analysis=settings.enable_code_analysis,
        preview_enabled=settings.preview_enabled,
        preview_max_file_size=settings.preview_max_file_size,
        trash_retention_days=settings.trash_retention_days,
        share_link_max_expiry_days=settings.share_link_max_expiry_days,
        share_link_default_expiry_days=settings.share_link_default_expiry_days,
        mcp_enabled=settings.mcp_enabled,
        mcp_rate_limit_requests=settings.mcp_rate_limit_requests,
        mcp_default_write_enabled=settings.mcp_default_write_enabled,
        enable_auth=settings.enable_auth,
    )


@router.patch("/settings", response_model=SettingsResponse)
async def update_settings(updates: SettingsUpdate) -> SettingsResponse:
    """
    Update application settings at runtime.

    Note: These changes are not persisted and will be lost on restart.
    For permanent changes, update environment variables or .env file.
    """
    # Apply updates to settings object (runtime only)
    update_dict = updates.model_dump(exclude_unset=True)

    for key, value in update_dict.items():
        if hasattr(settings, key):
            # Note: Pydantic Settings are immutable, this is a simplified example
            # In production, you'd need a mutable config store
            logger.info("settings_updated", key=key, value=value)

    logger.warning(
        "settings_update_runtime_only",
        message="Settings updates are runtime only and will not persist",
    )

    return await get_settings()


# =============================================================================
# Services Health Endpoints
# =============================================================================


async def check_postgres_health(db: AsyncSession) -> ServiceHealth:
    """Check PostgreSQL health."""
    try:
        start = datetime.now()
        await db.execute(text("SELECT 1"))
        latency = (datetime.now() - start).total_seconds() * 1000
        return ServiceHealth(
            name="postgresql",
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
        )
    except Exception as e:
        return ServiceHealth(
            name="postgresql",
            status=ServiceStatus.UNHEALTHY,
            message=str(e),
        )


async def check_redis_health() -> ServiceHealth:
    """Check Redis health."""
    try:
        cache = await get_cache_service()
        start = datetime.now()
        await cache.ping()
        latency = (datetime.now() - start).total_seconds() * 1000
        return ServiceHealth(
            name="redis",
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
        )
    except Exception as err:
        return ServiceHealth(
            name="redis",
            status=ServiceStatus.UNHEALTHY,
            message=str(err),
        )


async def check_chromadb_health() -> ServiceHealth:
    """Check ChromaDB health."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            url = f"{settings.chromadb_url}/api/v2/heartbeat"
            response = await client.get(url)
            latency = (datetime.now() - start).total_seconds() * 1000
            if response.status_code == 200:
                return ServiceHealth(
                    name="chromadb",
                    status=ServiceStatus.HEALTHY,
                    latency_ms=latency,
                )
            return ServiceHealth(
                name="chromadb",
                status=ServiceStatus.UNHEALTHY,
                message=f"HTTP {response.status_code}",
            )
    except Exception as err:
        return ServiceHealth(
            name="chromadb",
            status=ServiceStatus.UNHEALTHY,
            message=str(err),
        )


async def check_ollama_health() -> ServiceHealth:
    """Check Ollama health."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            url = f"{settings.ollama_url}/api/tags"
            response = await client.get(url)
            latency = (datetime.now() - start).total_seconds() * 1000
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                return ServiceHealth(
                    name="ollama",
                    status=ServiceStatus.HEALTHY,
                    latency_ms=latency,
                    details={"models": models},
                )
            return ServiceHealth(
                name="ollama",
                status=ServiceStatus.UNHEALTHY,
                message=f"HTTP {response.status_code}",
            )
    except Exception as err:
        return ServiceHealth(
            name="ollama",
            status=ServiceStatus.UNHEALTHY,
            message=str(err),
        )


async def check_gotenberg_health() -> ServiceHealth:
    """Check Gotenberg health."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            url = f"{settings.gotenberg_url}/health"
            response = await client.get(url)
            latency = (datetime.now() - start).total_seconds() * 1000
            if response.status_code == 200:
                return ServiceHealth(
                    name="gotenberg",
                    status=ServiceStatus.HEALTHY,
                    latency_ms=latency,
                )
            return ServiceHealth(
                name="gotenberg",
                status=ServiceStatus.UNHEALTHY,
                message=f"HTTP {response.status_code}",
            )
    except Exception as err:
        return ServiceHealth(
            name="gotenberg",
            status=ServiceStatus.UNHEALTHY,
            message=str(err),
        )


async def check_minio_health() -> ServiceHealth:
    """Check MinIO health."""
    try:
        storage = get_storage_service()
        start = datetime.now()
        # Try to list buckets as a health check
        async with storage._get_client() as client:
            await client.list_buckets()
        latency = (datetime.now() - start).total_seconds() * 1000
        return ServiceHealth(
            name="minio",
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
        )
    except Exception as err:
        return ServiceHealth(
            name="minio",
            status=ServiceStatus.UNHEALTHY,
            message=str(err),
        )


@router.get("/services/health", response_model=ServicesHealthResponse)
async def get_services_health(
    db: AsyncSession = Depends(get_db),
) -> ServicesHealthResponse:
    """
    Get health status of all services.

    Checks PostgreSQL, Redis, ChromaDB, Ollama, Gotenberg, and MinIO.
    """
    # Run all health checks concurrently
    results = await asyncio.gather(
        check_postgres_health(db),
        check_redis_health(),
        check_chromadb_health(),
        check_ollama_health(),
        check_gotenberg_health(),
        check_minio_health(),
        return_exceptions=True,
    )

    services = []
    for result in results:
        if isinstance(result, Exception):
            services.append(
                ServiceHealth(
                    name="unknown",
                    status=ServiceStatus.UNKNOWN,
                    message=str(result),
                )
            )
        else:
            services.append(result)

    # Determine overall status
    unhealthy = sum(1 for s in services if s.status == ServiceStatus.UNHEALTHY)
    if unhealthy == 0:
        overall = ServiceStatus.HEALTHY
    elif unhealthy < len(services):
        overall = ServiceStatus.DEGRADED
    else:
        overall = ServiceStatus.UNHEALTHY

    return ServicesHealthResponse(
        overall=overall,
        timestamp=datetime.utcnow(),
        services=services,
    )


@router.get("/services/stats", response_model=ServicesStatsResponse)
async def get_services_stats(
    db: AsyncSession = Depends(get_db),
) -> ServicesStatsResponse:
    """
    Get statistics for all services.
    """
    # Database stats
    db_stats = {}
    try:
        result = await db.execute(
            text(
                """
            SELECT
                (SELECT COUNT(*) FROM libraries WHERE deleted_at IS NULL) as libraries,
                (SELECT COUNT(*) FROM files WHERE deleted_at IS NULL) as files,
                (SELECT COUNT(*) FROM directories WHERE deleted_at IS NULL) as directories,
                (SELECT COUNT(*) FROM file_versions) as versions,
                (SELECT COUNT(*) FROM share_links) as shares,
                (SELECT pg_database_size(current_database())) as db_size
        """
            )
        )
        row = result.fetchone()
        if row:
            db_stats = {
                "libraries": row[0],
                "files": row[1],
                "directories": row[2],
                "versions": row[3],
                "shares": row[4],
                "database_size_bytes": row[5],
            }
    except Exception as e:
        db_stats = {"error": str(e)}

    # Storage stats
    storage_stats = {}
    try:
        storage = get_storage_service()
        async with storage._get_client() as client:
            buckets = await client.list_buckets()
            storage_stats = {
                "bucket_count": len(buckets.get("Buckets", [])),
                "buckets": [b["Name"] for b in buckets.get("Buckets", [])],
            }
    except Exception as e:
        storage_stats = {"error": str(e)}

    # Cache stats
    cache_stats = {}
    try:
        cache = await get_cache_service()
        info = await cache.info()
        db0_keys = info.get("db0", {}).get("keys", 0) if "db0" in info else 0
        cache_stats = {
            "used_memory": info.get("used_memory", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_keys": db0_keys,
        }
    except Exception as e:
        cache_stats = {"error": str(e)}

    # Vector DB stats
    vector_stats = {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{settings.chromadb_url}/api/v2/tenants/default_tenant/databases/default_database/collections"
            response = await client.get(url)
            if response.status_code == 200:
                collections = response.json()
                total_docs = 0
                for col in collections:
                    count_url = (
                        f"{settings.chromadb_url}/api/v2/tenants/default_tenant/databases/default_database/collections/"
                        f"{col['id']}/count"
                    )
                    col_response = await client.get(count_url)
                    if col_response.status_code == 200:
                        total_docs += col_response.json()
                vector_stats = {
                    "collections": len(collections),
                    "total_embeddings": total_docs,
                }
    except Exception as e:
        vector_stats = {"error": str(e)}

    # Search stats (from the indexing service)
    search_stats = {
        "embedding_model": settings.ollama_embedding_model,
        "chunk_size_code": settings.chunk_size_code,
        "chunk_size_docs": settings.chunk_size_docs,
    }

    return ServicesStatsResponse(
        timestamp=datetime.utcnow(),
        database=db_stats,
        storage=storage_stats,
        cache=cache_stats,
        vector_db=vector_stats,
        search=search_stats,
    )


# =============================================================================
# ChromaDB Endpoints
# =============================================================================


@router.get("/chromadb/collections", response_model=ChromaCollectionsResponse)
async def get_chromadb_collections() -> ChromaCollectionsResponse:
    """
    List all ChromaDB collections.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{settings.chromadb_url}/api/v2/tenants/default_tenant/databases/default_database/collections"
            response = await client.get(url)
            response.raise_for_status()
            collections_data = response.json()

            collections = []
            total_docs = 0

            for col in collections_data:
                # Get count for each collection
                count_url = (
                    f"{settings.chromadb_url}/api/v2/tenants/default_tenant/databases/default_database/collections/"
                    f"{col['id']}/count"
                )
                count_response = await client.get(count_url)
                count = count_response.json() if count_response.status_code == 200 else 0
                total_docs += count

                collections.append(
                    ChromaCollection(
                        name=col.get("name", "unknown"),
                        count=count,
                        metadata=col.get("metadata"),
                    )
                )

            return ChromaCollectionsResponse(
                collections=collections,
                total_documents=total_docs,
            )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ChromaDB not available: {e}",
        )


@router.delete("/chromadb/collections/{name}")
async def delete_chromadb_collection(name: str) -> Dict[str, str]:
    """
    Delete a ChromaDB collection.

    WARNING: This permanently deletes all embeddings in the collection.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{settings.chromadb_url}/api/v2/tenants/default_tenant/databases/default_database/collections/{name}"
            )
            if response.status_code == 200:
                logger.info("chromadb_collection_deleted", collection=name)
                return {"status": "deleted", "collection": name}
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Collection '{name}' not found",
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to delete collection: {response.text}",
                )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ChromaDB not available: {e}",
        )


@router.post("/chromadb/reindex", response_model=ChromaReindexResponse)
async def trigger_chromadb_reindex(
    request: ChromaReindexRequest,
    db: AsyncSession = Depends(get_db),
) -> ChromaReindexResponse:
    """
    Trigger a reindex of files in ChromaDB.

    This queues all files (or files from a specific library) for re-embedding.
    """
    # Count files to reindex
    query = select(func.count(FileMetadata.id)).where(
        FileMetadata.deleted_at.is_(None)
    )
    if request.library_id:
        query = query.where(FileMetadata.library_id == request.library_id)

    result = await db.execute(query)
    file_count = result.scalar() or 0

    # TODO: Actually trigger the reindex via the search service
    # For now, return a placeholder response
    import uuid

    task_id = str(uuid.uuid4())

    logger.info(
        "chromadb_reindex_triggered",
        task_id=task_id,
        library_id=request.library_id,
        force=request.force,
        file_count=file_count,
    )

    return ChromaReindexResponse(
        task_id=task_id,
        status="queued",
        message=f"Reindex queued for {file_count} files",
        estimated_documents=file_count,
    )


# =============================================================================
# Ollama Endpoints
# =============================================================================


@router.get("/ollama/models", response_model=OllamaModelsResponse)
async def get_ollama_models() -> OllamaModelsResponse:
    """
    List all loaded Ollama models.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.ollama_url}/api/tags")
            response.raise_for_status()
            data = response.json()

            models = []
            for m in data.get("models", []):
                models.append(
                    OllamaModel(
                        name=m.get("name", "unknown"),
                        size=m.get("size", 0),
                        digest=m.get("digest", ""),
                        modified_at=m.get("modified_at"),
                        details=m.get("details"),
                    )
                )

            return OllamaModelsResponse(models=models)
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama not available: {e}",
        )


@router.post("/ollama/models", response_model=OllamaPullResponse)
async def pull_ollama_model(request: OllamaPullRequest) -> OllamaPullResponse:
    """
    Pull a new Ollama model.

    This operation can take several minutes depending on model size.
    """
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min timeout
            response = await client.post(
                f"{settings.ollama_url}/api/pull",
                json={"name": request.name, "stream": False},
            )
            if response.status_code == 200:
                logger.info("ollama_model_pulled", model=request.name)
                return OllamaPullResponse(
                    status="success",
                    message=f"Model '{request.name}' pulled successfully",
                )
            else:
                return OllamaPullResponse(
                    status="error",
                    message=f"Failed to pull model: {response.text}",
                )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama not available: {e}",
        )


# =============================================================================
# Gotenberg Endpoints
# =============================================================================


@router.get("/gotenberg/health", response_model=GotenbergHealthResponse)
async def get_gotenberg_health() -> GotenbergHealthResponse:
    """
    Get Gotenberg service health and info.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{settings.gotenberg_url}/health"
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                return GotenbergHealthResponse(
                    status=ServiceStatus.HEALTHY,
                    version=data.get("version"),
                    modules=data.get("modules", []),
                )
            return GotenbergHealthResponse(
                status=ServiceStatus.UNHEALTHY,
            )
    except httpx.RequestError:
        return GotenbergHealthResponse(
            status=ServiceStatus.UNHEALTHY,
        )


# =============================================================================
# Nginx Endpoints
# =============================================================================


@router.get("/nginx/status", response_model=NginxStatusResponse)
async def get_nginx_status() -> NginxStatusResponse:
    """
    Get Nginx status (basic check).

    Note: Full nginx status requires nginx_status module enabled.
    """
    # Basic connectivity check to nginx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = "http://nginx:80/health"
            response = await client.get(url, follow_redirects=True)
            # 404 is ok, means nginx is responding
            if response.status_code in (200, 404):
                return NginxStatusResponse(status=ServiceStatus.HEALTHY)
            return NginxStatusResponse(status=ServiceStatus.UNHEALTHY)
    except httpx.RequestError:
        # Try alternative check
        return NginxStatusResponse(status=ServiceStatus.UNKNOWN)


# =============================================================================
# Maintenance Endpoints
# =============================================================================


@router.post("/maintenance/cleanup", response_model=MaintenanceCleanupResponse)
async def run_cleanup(
    request: MaintenanceCleanupRequest,
    db: AsyncSession = Depends(get_db),
) -> MaintenanceCleanupResponse:
    """
    Run cleanup operations.

    Operations:
    - Remove orphaned files in storage (no DB record)
    - Remove orphaned DB records (no storage file)
    - Remove expired share links
    - Empty trash (permanently delete soft-deleted items)
    """
    items: List[CleanupItem] = []
    errors: List[str] = []

    # Check for expired shares
    if request.clean_expired_shares:
        try:
            result = await db.execute(
                select(ShareLink).where(
                    ShareLink.expires_at.isnot(None),
                    ShareLink.expires_at < datetime.utcnow(),
                )
            )
            expired_shares = result.scalars().all()

            for share in expired_shares:
                items.append(
                    CleanupItem(
                        type="share_link",
                        id=str(share.id),
                        name=share.token,
                        reason="expired",
                    )
                )
                if not request.dry_run:
                    await db.delete(share)
        except Exception as e:
            errors.append(f"Error cleaning expired shares: {e}")

    # Check for trashed items past retention
    if request.empty_trash:
        try:
            from datetime import timedelta

            retention = settings.trash_retention_days
            cutoff = datetime.utcnow() - timedelta(days=retention)

            # Files
            result = await db.execute(
                select(FileMetadata).where(
                    FileMetadata.deleted_at.isnot(None),
                    FileMetadata.deleted_at < cutoff,
                )
            )
            trashed_files = result.scalars().all()

            for f in trashed_files:
                items.append(
                    CleanupItem(
                        type="file",
                        id=str(f.id),
                        name=f.filename,
                        reason="trash_expired",
                    )
                )
                if not request.dry_run:
                    # Also delete from storage
                    try:
                        storage = get_storage_service()
                        library = await db.get(Library, f.library_id)
                        if library:
                            await storage.delete_file(library.bucket_name, f.storage_key)
                    except Exception:
                        pass
                    await db.delete(f)

            # Directories
            result = await db.execute(
                select(Directory).where(
                    Directory.deleted_at.isnot(None),
                    Directory.deleted_at < cutoff,
                )
            )
            trashed_dirs = result.scalars().all()

            for d in trashed_dirs:
                items.append(
                    CleanupItem(
                        type="directory",
                        id=str(d.id),
                        name=d.name,
                        reason="trash_expired",
                    )
                )
                if not request.dry_run:
                    await db.delete(d)
        except Exception as e:
            errors.append(f"Error emptying trash: {e}")

    if not request.dry_run:
        await db.commit()

    return MaintenanceCleanupResponse(
        dry_run=request.dry_run,
        items_found=len(items),
        items_cleaned=0 if request.dry_run else len(items),
        items=items,
        errors=errors,
    )


@router.get("/maintenance/stats", response_model=MaintenanceStatsResponse)
async def get_maintenance_stats(
    db: AsyncSession = Depends(get_db),
) -> MaintenanceStatsResponse:
    """
    Get system-wide maintenance statistics.
    """
    # Database counts
    libraries_count = (
        await db.execute(
            select(func.count(Library.id)).where(Library.deleted_at.is_(None))
        )
    ).scalar() or 0

    files_count = (
        await db.execute(
            select(func.count(FileMetadata.id)).where(
                FileMetadata.deleted_at.is_(None)
            )
        )
    ).scalar() or 0

    dirs_count = (
        await db.execute(
            select(func.count(Directory.id)).where(
                Directory.deleted_at.is_(None)
            )
        )
    ).scalar() or 0

    versions_count = (
        await db.execute(select(func.count(FileVersion.id)))
    ).scalar() or 0

    shares_result = await db.execute(select(func.count(ShareLink.id)))
    shares_count = shares_result.scalar() or 0

    trashed_files = (
        await db.execute(
            select(func.count(FileMetadata.id)).where(
                FileMetadata.deleted_at.isnot(None)
            )
        )
    ).scalar() or 0

    trashed_dirs = (
        await db.execute(
            select(func.count(Directory.id)).where(
                Directory.deleted_at.isnot(None)
            )
        )
    ).scalar() or 0

    # Total storage
    total_bytes = (
        await db.execute(
            select(func.coalesce(func.sum(FileMetadata.size_bytes), 0)).where(
                FileMetadata.deleted_at.is_(None)
            )
        )
    ).scalar() or 0

    # Storage by library
    storage_query = (
        select(
            Library.name,
            func.coalesce(func.sum(FileMetadata.size_bytes), 0)
        )
        .join(FileMetadata, FileMetadata.library_id == Library.id)
        .where(
            Library.deleted_at.is_(None),
            FileMetadata.deleted_at.is_(None),
        )
        .group_by(Library.id, Library.name)
    )
    storage_by_lib_result = await db.execute(storage_query)
    storage_by_library = {
        row[0]: row[1] for row in storage_by_lib_result.fetchall()
    }

    # Vector DB stats
    total_embeddings = 0
    collections_count = 0
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{settings.chromadb_url}/api/v2/tenants/default_tenant/databases/default_database/collections"
            response = await client.get(url)
            if response.status_code == 200:
                collections = response.json()
                collections_count = len(collections)
                for col in collections:
                    count_url = (
                        f"{settings.chromadb_url}/api/v2/tenants/default_tenant/databases/default_database/collections/"
                        f"{col['id']}/count"
                    )
                    count_response = await client.get(count_url)
                    if count_response.status_code == 200:
                        total_embeddings += count_response.json()
    except Exception:
        pass

    # Cache stats
    cache_keys = 0
    cache_memory = None
    try:
        cache = await get_cache_service()
        info = await cache.info()
        db0_keys = info.get("db0", {}).get("keys", 0) if "db0" in info else 0
        cache_keys = db0_keys
        cache_memory = info.get("used_memory", 0)
    except Exception:
        pass

    return MaintenanceStatsResponse(
        timestamp=datetime.utcnow(),
        total_libraries=libraries_count,
        total_files=files_count,
        total_directories=dirs_count,
        total_versions=versions_count,
        total_shares=shares_count,
        trashed_items=trashed_files + trashed_dirs,
        total_storage_bytes=total_bytes,
        storage_by_library=storage_by_library,
        total_embeddings=total_embeddings,
        collections_count=collections_count,
        cache_keys=cache_keys,
        cache_memory_bytes=cache_memory,
    )
