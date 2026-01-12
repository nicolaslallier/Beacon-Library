"""Pydantic schemas for API request/response models."""

from app.schemas.library import (
    LibraryCreate,
    LibraryResponse,
    LibraryUpdate,
    LibraryListResponse,
)
from app.schemas.directory import (
    DirectoryCreate,
    DirectoryResponse,
    DirectoryUpdate,
    DirectoryMove,
)
from app.schemas.file import (
    FileResponse,
    FileUpdate,
    FileMove,
    FileVersionResponse,
    UploadInitResponse,
    UploadPartResponse,
    UploadCompleteRequest,
    DuplicateConflictResponse,
)
from app.schemas.browse import (
    BrowseItem,
    BrowseResponse,
)
from app.schemas.admin import (
    SettingsResponse,
    SettingsUpdate,
    ServiceHealth,
    ServicesHealthResponse,
    ServicesStatsResponse,
    ServiceStatus,
    ChromaCollectionsResponse,
    ChromaReindexRequest,
    ChromaReindexResponse,
    OllamaModelsResponse,
    OllamaPullRequest,
    OllamaPullResponse,
    MaintenanceCleanupRequest,
    MaintenanceCleanupResponse,
    MaintenanceStatsResponse,
)

__all__ = [
    # Library
    "LibraryCreate",
    "LibraryResponse",
    "LibraryUpdate",
    "LibraryListResponse",
    # Directory
    "DirectoryCreate",
    "DirectoryResponse",
    "DirectoryUpdate",
    "DirectoryMove",
    # File
    "FileResponse",
    "FileUpdate",
    "FileMove",
    "FileVersionResponse",
    "UploadInitResponse",
    "UploadPartResponse",
    "UploadCompleteRequest",
    "DuplicateConflictResponse",
    # Browse
    "BrowseItem",
    "BrowseResponse",
    # Admin
    "SettingsResponse",
    "SettingsUpdate",
    "ServiceHealth",
    "ServicesHealthResponse",
    "ServicesStatsResponse",
    "ServiceStatus",
    "ChromaCollectionsResponse",
    "ChromaReindexRequest",
    "ChromaReindexResponse",
    "OllamaModelsResponse",
    "OllamaPullRequest",
    "OllamaPullResponse",
    "MaintenanceCleanupRequest",
    "MaintenanceCleanupResponse",
    "MaintenanceStatsResponse",
]
