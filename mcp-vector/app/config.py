"""Configuration settings for MCP Vector Server."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Service identity
    service_name: str = "mcp-vector"
    service_version: str = "1.0.0"
    env: str = "local"

    # ChromaDB settings
    chromadb_host: str = "chromadb"
    chromadb_port: int = 8000

    @property
    def chromadb_url(self) -> str:
        return f"http://{self.chromadb_host}:{self.chromadb_port}"

    # Ollama settings
    ollama_host: str = "ollama"
    ollama_port: int = 11434
    ollama_embedding_model: str = "nomic-embed-text"

    @property
    def ollama_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"

    # PostgreSQL settings (for library metadata and access control)
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "beacon_user"
    postgres_password: str = "beacon_password"
    postgres_db: str = "beacon_library"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # MCP Server settings
    mcp_rate_limit_requests: int = 100
    mcp_rate_limit_window: int = 60  # seconds
    mcp_default_write_enabled: bool = False

    # Vector search settings
    default_top_k: int = 8
    max_top_k: int = 50
    low_confidence_threshold: float = 0.3  # Score below this is low confidence
    embedding_timeout: float = 30.0  # seconds

    # Observability
    otlp_endpoint: Optional[str] = None
    otlp_enabled: bool = False
    log_level: str = "INFO"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8001


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
