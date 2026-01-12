"""Pytest configuration and fixtures."""

import os
import uuid
from typing import AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Set test environment before importing app
os.environ["ENV"] = "test"
os.environ["CHROMADB_HOST"] = "localhost"
os.environ["CHROMADB_PORT"] = "8100"
os.environ["OLLAMA_HOST"] = "localhost"
os.environ["OLLAMA_PORT"] = "11434"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_USER"] = "test_user"
os.environ["POSTGRES_PASSWORD"] = "test_password"
os.environ["POSTGRES_DB"] = "test_db"


@pytest.fixture
def mock_embedding() -> list[float]:
    """Create a mock embedding vector."""
    # Return a simple 384-dimensional vector (nomic-embed-text dimension)
    return [0.1] * 384


@pytest.fixture
def mock_library_id() -> uuid.UUID:
    """Create a mock library UUID."""
    return uuid.UUID("12345678-1234-1234-1234-123456789012")


@pytest.fixture
def mock_file_id() -> str:
    """Create a mock file UUID."""
    return "abcd1234-abcd-1234-abcd-123456789abc"


@pytest.fixture
def sample_chunk_metadata(mock_library_id: uuid.UUID, mock_file_id: str) -> Dict:
    """Create sample chunk metadata."""
    return {
        "path": "/docs/test.md",
        "chunk_id": 0,
        "doc_id": mock_file_id,
        "library_id": str(mock_library_id),
        "line_start": 1,
        "line_end": 10,
        "language": "markdown",
        "chunk_type": "section",
        "file_name": "test.md",
    }


@pytest.fixture
def mock_chroma_service():
    """Create a mock ChromaDB service."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value=[
        {
            "id": "chunk-1",
            "text": "This is a test document about authentication.",
            "metadata": {
                "path": "/docs/auth.md",
                "chunk_index": 0,
                "doc_id": "file-123",
                "library_id": "lib-123",
                "line_start": 1,
                "line_end": 10,
            },
            "score": 0.85,
            "distance": 0.15,
        }
    ])
    mock.upsert_documents = AsyncMock(return_value=True)
    mock.get_documents = AsyncMock(return_value=[])
    mock.delete_by_filter = AsyncMock(return_value=1)
    mock.delete_by_doc_id = AsyncMock(return_value=1)
    mock.delete_collection = AsyncMock(return_value=True)
    mock.get_collection_count = AsyncMock(return_value=10)
    mock.list_collections = MagicMock(return_value=["beacon_lib_test"])
    return mock


@pytest.fixture
def mock_embedding_service(mock_embedding: list[float]):
    """Create a mock embedding service."""
    mock = MagicMock()
    mock.generate_embedding = AsyncMock(return_value=mock_embedding)
    mock.generate_embeddings_batch = AsyncMock(return_value=[mock_embedding])
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_access_service(mock_library_id: uuid.UUID):
    """Create a mock access control service."""
    mock = MagicMock()
    mock.initialize = AsyncMock()
    mock.close = AsyncMock()
    mock.check_rate_limit = MagicMock(return_value=True)
    mock.get_rate_limit_remaining = MagicMock(return_value=99)
    mock.check_library_access = AsyncMock(return_value=True)
    mock.get_accessible_libraries = AsyncMock(return_value=[mock_library_id])
    mock.library_exists = AsyncMock(return_value=True)
    return mock
