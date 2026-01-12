"""Admin API schemas for request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class ServiceStatus(str, Enum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"


class MaintenanceAction(str, Enum):
    """Maintenance action types."""

    REINDEX = "reindex"
    CLEANUP = "cleanup"
    VACUUM = "vacuum"
    CACHE_CLEAR = "cache_clear"


# =============================================================================
# Settings Schemas
# =============================================================================


class SettingsResponse(BaseModel):
    """Current application settings."""

    # Application
    app_name: str
    app_version: str
    env: str
    debug: bool

    # Database
    db_pool_size: int
    db_max_overflow: int

    # Storage
    storage_max_file_size: int
    storage_chunk_size: int
    storage_presigned_url_expiry: int

    # Search/Indexing
    chunk_size_code: int
    chunk_size_docs: int
    chunk_overlap: int
    max_chunks_per_file: int
    enable_code_analysis: bool

    # Preview
    preview_enabled: bool
    preview_max_file_size: int

    # Trash
    trash_retention_days: int

    # Share Links
    share_link_max_expiry_days: int
    share_link_default_expiry_days: Optional[int]

    # MCP
    mcp_enabled: bool
    mcp_rate_limit_requests: int
    mcp_default_write_enabled: bool

    # Auth
    enable_auth: bool


class SettingsUpdate(BaseModel):
    """Update application settings (runtime only, not persisted)."""

    # Search/Indexing
    chunk_size_code: Optional[int] = Field(None, ge=100, le=10000)
    chunk_size_docs: Optional[int] = Field(None, ge=100, le=10000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000)
    max_chunks_per_file: Optional[int] = Field(None, ge=1, le=500)
    enable_code_analysis: Optional[bool] = None

    # Preview
    preview_enabled: Optional[bool] = None
    preview_max_file_size: Optional[int] = Field(None, ge=1024)

    # Trash
    trash_retention_days: Optional[int] = Field(None, ge=1, le=365)

    # MCP
    mcp_rate_limit_requests: Optional[int] = Field(None, ge=1)
    mcp_default_write_enabled: Optional[bool] = None


# =============================================================================
# Service Health Schemas
# =============================================================================


class ServiceHealth(BaseModel):
    """Individual service health status."""

    name: str
    status: ServiceStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ServicesHealthResponse(BaseModel):
    """Health status of all services."""

    overall: ServiceStatus
    timestamp: datetime
    services: List[ServiceHealth]


class ServiceStats(BaseModel):
    """Statistics for a service."""

    name: str
    stats: Dict[str, Any]


class ServicesStatsResponse(BaseModel):
    """Statistics for all services."""

    timestamp: datetime
    database: Dict[str, Any]
    storage: Dict[str, Any]
    cache: Dict[str, Any]
    vector_db: Dict[str, Any]
    search: Dict[str, Any]


# =============================================================================
# ChromaDB Schemas
# =============================================================================


class ChromaCollection(BaseModel):
    """ChromaDB collection info."""

    name: str
    count: int
    metadata: Optional[Dict[str, Any]] = None


class ChromaCollectionsResponse(BaseModel):
    """List of ChromaDB collections."""

    collections: List[ChromaCollection]
    total_documents: int


class ChromaReindexRequest(BaseModel):
    """Request to reindex ChromaDB."""

    library_id: Optional[str] = Field(
        None,
        description="Specific library to reindex, or all if not specified",
    )
    force: bool = Field(
        False, description="Force reindex even if already indexed"
    )


class ChromaReindexResponse(BaseModel):
    """Response from reindex operation."""

    task_id: str
    status: str
    message: str
    estimated_documents: int


# =============================================================================
# Ollama Schemas
# =============================================================================


class OllamaModel(BaseModel):
    """Ollama model info."""

    name: str
    size: int
    digest: str
    modified_at: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None


class OllamaModelsResponse(BaseModel):
    """List of Ollama models."""

    models: List[OllamaModel]


class OllamaPullRequest(BaseModel):
    """Request to pull an Ollama model."""

    name: str = Field(
        ...,
        description="Model name to pull (e.g., nomic-embed-text)",
    )


class OllamaPullResponse(BaseModel):
    """Response from model pull operation."""

    status: str
    message: str


# =============================================================================
# Gotenberg Schemas
# =============================================================================


class GotenbergHealthResponse(BaseModel):
    """Gotenberg service health."""

    status: ServiceStatus
    version: Optional[str] = None
    modules: Optional[List[str]] = None


# =============================================================================
# Nginx Schemas
# =============================================================================


class NginxStatusResponse(BaseModel):
    """Nginx status information."""

    status: ServiceStatus
    active_connections: Optional[int] = None
    requests_per_second: Optional[float] = None
    uptime_seconds: Optional[int] = None


# =============================================================================
# Maintenance Schemas
# =============================================================================


class MaintenanceCleanupRequest(BaseModel):
    """Request for cleanup operation."""

    dry_run: bool = Field(
        True, description="If true, only report what would be deleted"
    )
    clean_orphaned_files: bool = Field(
        True, description="Remove files in storage without DB records"
    )
    clean_orphaned_records: bool = Field(
        True, description="Remove DB records without storage files"
    )
    clean_expired_shares: bool = Field(
        True, description="Remove expired share links"
    )
    empty_trash: bool = Field(
        False, description="Permanently delete all trashed items"
    )


class CleanupItem(BaseModel):
    """Item that would be or was cleaned up."""

    type: str
    id: str
    name: Optional[str] = None
    reason: str


class MaintenanceCleanupResponse(BaseModel):
    """Response from cleanup operation."""

    dry_run: bool
    items_found: int
    items_cleaned: int
    items: List[CleanupItem]
    errors: List[str]


class MaintenanceStatsResponse(BaseModel):
    """System-wide maintenance statistics."""

    timestamp: datetime

    # Database stats
    total_libraries: int
    total_files: int
    total_directories: int
    total_versions: int
    total_shares: int
    trashed_items: int

    # Storage stats
    total_storage_bytes: int
    storage_by_library: Dict[str, int]

    # Vector DB stats
    total_embeddings: int
    collections_count: int

    # Cache stats
    cache_keys: int
    cache_memory_bytes: Optional[int] = None


# =============================================================================
# User/Permission Schemas
# =============================================================================


class UserPermission(BaseModel):
    """User permission info."""

    user_id: str
    username: str
    email: Optional[str] = None
    roles: List[str]
    libraries: List[str]
    is_admin: bool


class UsersResponse(BaseModel):
    """List of users with permissions."""

    users: List[UserPermission]
    total: int


class UpdatePermissionsRequest(BaseModel):
    """Request to update user permissions."""

    roles: Optional[List[str]] = None
    libraries: Optional[List[str]] = None
    is_admin: Optional[bool] = None
