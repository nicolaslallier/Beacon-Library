"""Tests for MCP Vector Server API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHealthEndpoints:
    """Tests for health and status endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client with mocked services."""
        with patch("app.main.setup_logging"):
            with patch("app.main.setup_tracing"):
                with patch("app.main.AccessControlService") as mock_access:
                    mock_access_instance = MagicMock()
                    mock_access_instance.initialize = AsyncMock()
                    mock_access_instance.close = AsyncMock()
                    mock_access_instance.check_rate_limit = MagicMock(return_value=True)
                    mock_access.return_value = mock_access_instance

                    with patch("app.main.OllamaEmbeddingService") as mock_ollama:
                        mock_ollama_instance = MagicMock()
                        mock_ollama_instance.health_check = AsyncMock(return_value=True)
                        mock_ollama.return_value = mock_ollama_instance

                        from fastapi.testclient import TestClient
                        from app.main import app

                        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "mcp-vector"

    def test_healthz_endpoint(self, client):
        """Test /healthz endpoint (alias)."""
        response = client.get("/healthz")
        assert response.status_code == 200


class TestMCPToolEndpoints:
    """Tests for MCP tool endpoints."""

    @pytest.fixture
    def client_with_mocks(self, mock_chroma_service, mock_embedding_service, mock_access_service):
        """Create a test client with mocked services."""
        with patch("app.main.setup_logging"):
            with patch("app.main.setup_tracing"):
                with patch("app.main.AccessControlService") as mock_access_cls:
                    mock_access_cls.return_value = mock_access_service

                    with patch("app.main.OllamaEmbeddingService") as mock_ollama:
                        mock_ollama.return_value = mock_embedding_service

                        with patch("app.mcp.tools.ChromaDBService") as mock_chroma:
                            mock_chroma.return_value = mock_chroma_service

                            with patch("app.mcp.tools.OllamaEmbeddingService") as mock_emb:
                                mock_emb.return_value = mock_embedding_service

                                from fastapi.testclient import TestClient
                                from app.main import app

                                return TestClient(app)

    def test_list_tools(self, client_with_mocks):
        """Test GET /mcp/tools endpoint."""
        response = client_with_mocks.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data

        tool_names = [t["name"] for t in data["tools"]]
        assert "vector.query" in tool_names
        assert "vector.upsert_documents" in tool_names
        assert "vector.get" in tool_names
        assert "vector.delete" in tool_names

    def test_call_unknown_tool(self, client_with_mocks):
        """Test calling an unknown tool."""
        response = client_with_mocks.post(
            "/mcp/tools/unknown.tool",
            json={"arguments": {}},
        )
        assert response.status_code == 404


class TestVectorQueryTool:
    """Tests for vector.query tool."""

    @pytest.fixture
    def client_with_mocks(self, mock_chroma_service, mock_embedding_service, mock_access_service):
        """Create a test client with mocked services."""
        with patch("app.main.setup_logging"):
            with patch("app.main.setup_tracing"):
                with patch("app.main.AccessControlService") as mock_access_cls:
                    mock_access_cls.return_value = mock_access_service

                    with patch("app.main.OllamaEmbeddingService") as mock_ollama:
                        mock_ollama.return_value = mock_embedding_service

                        with patch("app.mcp.tools.ChromaDBService") as mock_chroma:
                            mock_chroma.return_value = mock_chroma_service

                            with patch("app.mcp.tools.OllamaEmbeddingService") as mock_emb:
                                mock_emb.return_value = mock_embedding_service

                                from fastapi.testclient import TestClient
                                from app.main import app

                                return TestClient(app)

    def test_query_basic(self, client_with_mocks):
        """Test basic vector query."""
        response = client_with_mocks.post(
            "/mcp/tools/vector.query",
            json={
                "arguments": {
                    "text": "How does authentication work?",
                    "top_k": 5,
                }
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert "query_id" in data
        assert "low_confidence" in data

    def test_query_with_filters(self, client_with_mocks):
        """Test vector query with filters."""
        response = client_with_mocks.post(
            "/mcp/tools/vector.query",
            json={
                "arguments": {
                    "text": "authentication",
                    "top_k": 3,
                    "filters": {
                        "language": "python",
                        "chunk_type": "function",
                    },
                }
            },
        )
        assert response.status_code == 200


class TestVectorUpsertTool:
    """Tests for vector.upsert_documents tool."""

    @pytest.fixture
    def client_with_mocks(self, mock_chroma_service, mock_embedding_service, mock_access_service):
        """Create a test client with mocked services."""
        # Enable write access for upsert tests
        mock_access_service.check_library_access = AsyncMock(return_value=True)

        with patch("app.main.setup_logging"):
            with patch("app.main.setup_tracing"):
                with patch("app.main.AccessControlService") as mock_access_cls:
                    mock_access_cls.return_value = mock_access_service

                    with patch("app.main.OllamaEmbeddingService") as mock_ollama:
                        mock_ollama.return_value = mock_embedding_service

                        with patch("app.mcp.tools.ChromaDBService") as mock_chroma:
                            mock_chroma.return_value = mock_chroma_service

                            with patch("app.mcp.tools.OllamaEmbeddingService") as mock_emb:
                                mock_emb.return_value = mock_embedding_service

                                from fastapi.testclient import TestClient
                                from app.main import app

                                return TestClient(app)

    def test_upsert_basic(self, client_with_mocks, sample_chunk_metadata):
        """Test basic upsert operation."""
        response = client_with_mocks.post(
            "/mcp/tools/vector.upsert_documents",
            json={
                "arguments": {
                    "chunks": ["This is test content about authentication."],
                    "metadata": [sample_chunk_metadata],
                }
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "upserted_count" in data
        assert "ids" in data
        assert "errors" in data


class TestVectorDeleteTool:
    """Tests for vector.delete tool."""

    @pytest.fixture
    def client_with_mocks(self, mock_chroma_service, mock_embedding_service, mock_access_service):
        """Create a test client with mocked services."""
        mock_access_service.check_library_access = AsyncMock(return_value=True)

        with patch("app.main.setup_logging"):
            with patch("app.main.setup_tracing"):
                with patch("app.main.AccessControlService") as mock_access_cls:
                    mock_access_cls.return_value = mock_access_service

                    with patch("app.main.OllamaEmbeddingService") as mock_ollama:
                        mock_ollama.return_value = mock_embedding_service

                        with patch("app.mcp.tools.ChromaDBService") as mock_chroma:
                            mock_chroma.return_value = mock_chroma_service

                            with patch("app.mcp.tools.OllamaEmbeddingService") as mock_emb:
                                mock_emb.return_value = mock_embedding_service

                                from fastapi.testclient import TestClient
                                from app.main import app

                                return TestClient(app)

    def test_delete_by_doc_id(self, client_with_mocks):
        """Test delete by doc_id."""
        response = client_with_mocks.post(
            "/mcp/tools/vector.delete",
            json={
                "arguments": {
                    "where": {
                        "doc_id": "doc-123",
                    }
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "deleted_count" in data
