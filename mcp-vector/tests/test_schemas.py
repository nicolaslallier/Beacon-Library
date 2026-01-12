"""Tests for vector schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.vector import (
    QueryInput,
    QueryOutput,
    QueryResult,
    QueryResultMetadata,
    QueryFilters,
    UpsertInput,
    UpsertMetadata,
    UpsertOutput,
    GetInput,
    GetOutput,
    DeleteInput,
    DeleteWhere,
)


class TestQuerySchemas:
    """Tests for vector.query schemas."""

    def test_query_input_minimal(self):
        """Test minimal query input."""
        data = QueryInput(text="test query")
        assert data.text == "test query"
        assert data.top_k == 8  # default
        assert data.filters is None

    def test_query_input_with_filters(self):
        """Test query input with filters."""
        data = QueryInput(
            text="authentication",
            top_k=5,
            filters=QueryFilters(
                library_id="12345678-1234-1234-1234-123456789012",
                language="python",
            ),
        )
        assert data.top_k == 5
        assert data.filters.library_id == "12345678-1234-1234-1234-123456789012"
        assert data.filters.language == "python"

    def test_query_input_top_k_limits(self):
        """Test top_k validation."""
        # Valid
        data = QueryInput(text="test", top_k=1)
        assert data.top_k == 1

        data = QueryInput(text="test", top_k=50)
        assert data.top_k == 50

        # Invalid - too low
        with pytest.raises(ValidationError):
            QueryInput(text="test", top_k=0)

        # Invalid - too high
        with pytest.raises(ValidationError):
            QueryInput(text="test", top_k=51)

    def test_query_input_empty_text(self):
        """Test empty text validation."""
        with pytest.raises(ValidationError):
            QueryInput(text="")

    def test_query_result_metadata(self):
        """Test query result metadata."""
        metadata = QueryResultMetadata(
            path="/docs/auth.md",
            chunk_id=0,
            doc_id="file-123",
            line_start=1,
            line_end=10,
        )
        assert metadata.path == "/docs/auth.md"
        assert metadata.chunk_id == 0

    def test_query_result(self):
        """Test query result."""
        result = QueryResult(
            id="chunk-1",
            text="Test content",
            score=0.85,
            metadata=QueryResultMetadata(path="/test.md", chunk_id=0),
        )
        assert result.score == 0.85

    def test_query_output(self):
        """Test query output."""
        output = QueryOutput(
            results=[],
            low_confidence=True,
            query_id="query-123",
        )
        assert output.low_confidence is True
        assert output.query_id == "query-123"


class TestUpsertSchemas:
    """Tests for vector.upsert_documents schemas."""

    def test_upsert_input_valid(self):
        """Test valid upsert input."""
        data = UpsertInput(
            chunks=["chunk 1 content", "chunk 2 content"],
            metadata=[
                UpsertMetadata(
                    path="/docs/test.md",
                    chunk_id=0,
                    library_id="lib-123",
                ),
                UpsertMetadata(
                    path="/docs/test.md",
                    chunk_id=1,
                    library_id="lib-123",
                ),
            ],
        )
        assert len(data.chunks) == 2
        assert len(data.metadata) == 2

    def test_upsert_metadata_required_fields(self):
        """Test required fields in upsert metadata."""
        # Valid with required fields
        meta = UpsertMetadata(
            path="/test.md",
            chunk_id=0,
            library_id="lib-123",
        )
        assert meta.path == "/test.md"

        # Missing required field
        with pytest.raises(ValidationError):
            UpsertMetadata(path="/test.md", chunk_id=0)  # Missing library_id

    def test_upsert_output(self):
        """Test upsert output."""
        output = UpsertOutput(
            upserted_count=2,
            ids=["chunk-1", "chunk-2"],
            errors=[],
        )
        assert output.upserted_count == 2


class TestGetSchemas:
    """Tests for vector.get schemas."""

    def test_get_input(self):
        """Test get input."""
        data = GetInput(ids=["chunk-1", "chunk-2"])
        assert len(data.ids) == 2

    def test_get_input_empty(self):
        """Test empty get input."""
        with pytest.raises(ValidationError):
            GetInput(ids=[])

    def test_get_output(self):
        """Test get output."""
        output = GetOutput(items=[])
        assert len(output.items) == 0


class TestDeleteSchemas:
    """Tests for vector.delete schemas."""

    def test_delete_input_doc_id(self):
        """Test delete by doc_id."""
        data = DeleteInput(where=DeleteWhere(doc_id="doc-123"))
        assert data.where.doc_id == "doc-123"

    def test_delete_input_path_prefix(self):
        """Test delete by path prefix."""
        data = DeleteInput(where=DeleteWhere(path_prefix="/docs/"))
        assert data.where.path_prefix == "/docs/"

    def test_delete_input_library_id(self):
        """Test delete by library_id."""
        data = DeleteInput(where=DeleteWhere(library_id="lib-123"))
        assert data.where.library_id == "lib-123"
