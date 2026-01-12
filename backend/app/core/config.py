"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================================
    # Application
    # ==========================================================================
    app_name: str = Field(default="Beacon Library", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    env: str = Field(default="local", description="Environment (local, dev, staging, prod)")
    base_url: str = Field(
        default="http://localhost:8181",
        description="Base URL for the application (used for share links)",
    )

    # ==========================================================================
    # API Configuration
    # ==========================================================================
    api_prefix: str = Field(default="/api", description="API route prefix")
    api_version: str = Field(default="v1", description="Current API version")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # ==========================================================================
    # Database (PostgreSQL)
    # ==========================================================================
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(default="beacon_user", description="PostgreSQL user")
    postgres_password: str = Field(default="beacon_password", description="PostgreSQL password")
    postgres_db: str = Field(default="beacon_library", description="PostgreSQL database name")

    # Connection pool settings
    db_pool_size: int = Field(default=5, description="Database connection pool size")
    db_max_overflow: int = Field(default=10, description="Max overflow connections")
    db_pool_timeout: int = Field(default=30, description="Pool timeout in seconds")

    @property
    def database_url(self) -> str:
        """Construct the async database URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Construct the sync database URL (for Alembic)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ==========================================================================
    # Redis
    # ==========================================================================
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")

    # Cache settings
    cache_ttl_seconds: int = Field(default=300, description="Default cache TTL in seconds")
    cache_prefix: str = Field(default="beacon:", description="Cache key prefix")

    @property
    def redis_url(self) -> str:
        """Construct the Redis URL."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ==========================================================================
    # MinIO (S3-compatible storage)
    # ==========================================================================
    minio_endpoint: str = Field(default="localhost:9000", description="MinIO endpoint")
    minio_access_key: str = Field(default="minioadmin", description="MinIO access key")
    minio_secret_key: str = Field(default="minioadmin", description="MinIO secret key")
    minio_secure: bool = Field(default=False, description="Use HTTPS for MinIO")
    minio_region: str = Field(default="us-east-1", description="MinIO region")

    # Storage settings
    storage_bucket_prefix: str = Field(default="beacon-lib-", description="Bucket name prefix")
    storage_max_file_size: int = Field(
        default=100 * 1024 * 1024,  # 100 MB
        description="Maximum file size in bytes",
    )
    storage_chunk_size: int = Field(
        default=5 * 1024 * 1024,  # 5 MB
        description="Chunk size for multipart uploads",
    )
    storage_presigned_url_expiry: int = Field(
        default=3600,  # 1 hour
        description="Presigned URL expiry in seconds",
    )

    @property
    def minio_endpoint_url(self) -> str:
        """Construct the MinIO endpoint URL."""
        protocol = "https" if self.minio_secure else "http"
        return f"{protocol}://{self.minio_endpoint}"

    # ==========================================================================
    # Keycloak
    # ==========================================================================
    keycloak_url: str = Field(
        default="http://localhost:8080",
        description="Keycloak server URL",
    )
    keycloak_realm: str = Field(default="beacon", description="Keycloak realm name")
    keycloak_client_id: str = Field(
        default="beacon-library",
        description="Keycloak client ID for the application",
    )
    keycloak_client_secret: Optional[str] = Field(
        default=None,
        description="Keycloak client secret (for confidential clients)",
    )
    keycloak_guest_client_id: str = Field(
        default="beacon-library-guest",
        description="Keycloak client ID for guest access",
    )

    # Token validation settings
    keycloak_verify_token: bool = Field(
        default=True,
        description="Verify JWT token signature",
    )
    keycloak_audience: Optional[str] = Field(
        default=None,
        description="Expected JWT audience (defaults to client_id)",
    )
    
    # Authentication control
    enable_auth: bool = Field(
        default=True,
        description="Enable authentication (set to False for development)",
    )

    @property
    def keycloak_issuer(self) -> str:
        """Construct the Keycloak issuer URL."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_jwks_url(self) -> str:
        """Construct the Keycloak JWKS URL."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"

    @property
    def keycloak_token_url(self) -> str:
        """Construct the Keycloak token endpoint URL."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/token"

    # ==========================================================================
    # MCP Server
    # ==========================================================================
    mcp_enabled: bool = Field(default=True, description="Enable MCP server")
    mcp_rate_limit_requests: int = Field(
        default=100,
        description="MCP rate limit: requests per minute per agent",
    )
    mcp_rate_limit_window: int = Field(
        default=60,
        description="MCP rate limit window in seconds",
    )
    mcp_default_write_enabled: bool = Field(
        default=False,
        description="Default MCP write permission for new libraries",
    )

    # ==========================================================================
    # Search (ChromaDB + Ollama)
    # ==========================================================================
    chromadb_host: str = Field(default="localhost", description="ChromaDB host")
    chromadb_port: int = Field(default=8000, description="ChromaDB port")

    ollama_host: str = Field(default="localhost", description="Ollama host")
    ollama_port: int = Field(default=11434, description="Ollama port")
    ollama_embedding_model: str = Field(
        default="nomic-embed-text",
        description="Ollama embedding model",
    )

    @property
    def chromadb_url(self) -> str:
        """Construct the ChromaDB URL."""
        return f"http://{self.chromadb_host}:{self.chromadb_port}"

    @property
    def ollama_url(self) -> str:
        """Construct the Ollama URL."""
        return f"http://{self.ollama_host}:{self.ollama_port}"

    # ==========================================================================
    # Vector Search Chunking
    # ==========================================================================
    chunk_size_code: int = Field(
        default=1500,
        description="Target chunk size in tokens for code files",
    )
    chunk_size_docs: int = Field(
        default=1000,
        description="Target chunk size in tokens for documentation files",
    )
    chunk_overlap: int = Field(
        default=200,
        description="Overlap in tokens between consecutive chunks",
    )
    max_chunks_per_file: int = Field(
        default=50,
        description="Maximum number of chunks per file",
    )
    enable_code_analysis: bool = Field(
        default=True,
        description="Enable advanced code analysis for indexing",
    )

    # ==========================================================================
    # File Preview (Gotenberg/LibreOffice)
    # ==========================================================================
    gotenberg_url: str = Field(
        default="http://localhost:3000",
        description="Gotenberg URL for document conversion",
    )
    preview_enabled: bool = Field(default=True, description="Enable file previews")
    preview_max_file_size: int = Field(
        default=50 * 1024 * 1024,  # 50 MB
        description="Maximum file size for preview generation",
    )

    # ==========================================================================
    # Email (SMTP)
    # ==========================================================================
    smtp_host: str = Field(default="localhost", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP")
    smtp_from_email: str = Field(
        default="noreply@beacon.local",
        description="From email address",
    )
    smtp_from_name: str = Field(
        default="Beacon Library",
        description="From name",
    )

    # ==========================================================================
    # Observability
    # ==========================================================================
    otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OpenTelemetry OTLP endpoint",
    )
    otlp_enabled: bool = Field(default=True, description="Enable OTLP tracing")
    log_level: str = Field(default="INFO", description="Logging level")
    log_json: bool = Field(default=True, description="Use JSON logging format")

    # ==========================================================================
    # Trash / Soft Delete
    # ==========================================================================
    trash_retention_days: int = Field(
        default=30,
        description="Days to retain soft-deleted items",
    )

    # ==========================================================================
    # Share Links
    # ==========================================================================
    share_link_max_expiry_days: int = Field(
        default=365,
        description="Maximum expiry days for share links",
    )
    share_link_default_expiry_days: Optional[int] = Field(
        default=None,
        description="Default expiry days for share links (None = no expiry)",
    )

    # ==========================================================================
    # Validation
    # ==========================================================================
    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        """Validate environment value."""
        allowed = {"local", "dev", "staging", "prod"}
        if v not in allowed:
            raise ValueError(f"env must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
