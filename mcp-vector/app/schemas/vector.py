"""Pydantic schemas for vector MCP tools."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ============================================================================
# vector.query schemas
# ============================================================================


class QueryFilters(BaseModel):
    """Filters for vector.query."""

    path: Optional[str] = Field(
        None,
        description="Exact path or path prefix to filter results",
    )
    doc_id: Optional[str] = Field(
        None,
        description="Document ID (file UUID) to filter results",
    )
    library_id: Optional[str] = Field(
        None,
        description="Library UUID to scope the search",
    )
    doc_type: Optional[str] = Field(
        None,
        description="MIME type filter (e.g., 'text/python', 'application/pdf')",
    )
    language: Optional[str] = Field(
        None,
        description="Programming language filter (e.g., 'python', 'javascript')",
    )
    chunk_type: Optional[str] = Field(
        None,
        description="Chunk type filter (function, class, section, etc.)",
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Tag filter (AND logic)",
    )


class QueryInput(BaseModel):
    """Input schema for vector.query tool."""

    text: str = Field(
        ...,
        description="Query text for semantic search",
        min_length=1,
    )
    top_k: int = Field(
        default=8,
        ge=1,
        le=50,
        description="Number of results to return",
    )
    filters: Optional[QueryFilters] = Field(
        None,
        description="Optional metadata filters",
    )


class QueryResultMetadata(BaseModel):
    """Metadata for a single query result."""

    path: str = Field(
        ...,
        description="File path (can be used with fs.read)",
    )
    chunk_id: int = Field(
        ...,
        description="Chunk index within the document",
    )
    doc_id: Optional[str] = Field(
        None,
        description="Document/file UUID",
    )
    library_id: Optional[str] = Field(
        None,
        description="Library UUID",
    )
    line_start: Optional[int] = Field(
        None,
        description="Starting line number (for code files)",
    )
    line_end: Optional[int] = Field(
        None,
        description="Ending line number (for code files)",
    )
    page: Optional[int] = Field(
        None,
        description="Page number (for PDFs)",
    )
    offset_start: Optional[int] = Field(
        None,
        description="Character offset start",
    )
    offset_end: Optional[int] = Field(
        None,
        description="Character offset end",
    )
    language: Optional[str] = Field(
        None,
        description="Programming language",
    )
    chunk_type: Optional[str] = Field(
        None,
        description="Type of chunk (function, class, section, etc.)",
    )
    name: Optional[str] = Field(
        None,
        description="Name of the code element (function/class name)",
    )
    heading: Optional[str] = Field(
        None,
        description="Section heading (for markdown)",
    )
    file_name: Optional[str] = Field(
        None,
        description="Original file name",
    )


class QueryResult(BaseModel):
    """A single result from vector.query."""

    id: str = Field(
        ...,
        description="Unique chunk identifier",
    )
    text: str = Field(
        ...,
        description="Chunk content",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (1.0 = best match)",
    )
    metadata: QueryResultMetadata = Field(
        ...,
        description="Chunk metadata for traceability",
    )


class QueryOutput(BaseModel):
    """Output schema for vector.query tool."""

    results: List[QueryResult] = Field(
        default_factory=list,
        description="List of matching chunks sorted by relevance",
    )
    low_confidence: bool = Field(
        default=False,
        description="True if all results are below confidence threshold",
    )
    query_id: str = Field(
        ...,
        description="Unique query identifier for audit logging",
    )


# ============================================================================
# vector.upsert_documents schemas
# ============================================================================


class UpsertMetadata(BaseModel):
    """Metadata for a single chunk to upsert."""

    path: str = Field(
        ...,
        description="File path (required for traceability)",
    )
    chunk_id: int = Field(
        ...,
        ge=0,
        description="Chunk index within document (required for idempotence)",
    )
    doc_id: Optional[str] = Field(
        None,
        description="Document/file UUID (recommended)",
    )
    library_id: str = Field(
        ...,
        description="Library UUID (required)",
    )
    line_start: Optional[int] = Field(
        None,
        description="Starting line number",
    )
    line_end: Optional[int] = Field(
        None,
        description="Ending line number",
    )
    page: Optional[int] = Field(
        None,
        description="Page number (for PDFs)",
    )
    offset_start: Optional[int] = Field(
        None,
        description="Character offset start",
    )
    offset_end: Optional[int] = Field(
        None,
        description="Character offset end",
    )
    hash: Optional[str] = Field(
        None,
        description="Chunk content fingerprint for change detection",
    )
    updated_at: Optional[str] = Field(
        None,
        description="ISO-8601 timestamp of last update",
    )
    language: Optional[str] = Field(
        None,
        description="Programming language",
    )
    chunk_type: Optional[str] = Field(
        None,
        description="Type of chunk (function, class, section, etc.)",
    )
    name: Optional[str] = Field(
        None,
        description="Name of the code element",
    )
    file_name: Optional[str] = Field(
        None,
        description="Original file name",
    )
    mime_type: Optional[str] = Field(
        None,
        description="MIME type of the source file",
    )


class UpsertInput(BaseModel):
    """Input schema for vector.upsert_documents tool."""

    chunks: List[str] = Field(
        ...,
        description="List of chunk texts to upsert",
        min_length=1,
    )
    metadata: List[UpsertMetadata] = Field(
        ...,
        description="Metadata for each chunk (must align 1:1 with chunks)",
        min_length=1,
    )


class UpsertError(BaseModel):
    """Error details for a failed upsert."""

    index: int = Field(
        ...,
        description="Index of the chunk that failed",
    )
    error: str = Field(
        ...,
        description="Error message",
    )


class UpsertOutput(BaseModel):
    """Output schema for vector.upsert_documents tool."""

    upserted_count: int = Field(
        ...,
        description="Number of chunks successfully upserted",
    )
    ids: List[str] = Field(
        default_factory=list,
        description="IDs of upserted chunks",
    )
    errors: List[UpsertError] = Field(
        default_factory=list,
        description="Errors for failed chunks (if any)",
    )


# ============================================================================
# vector.get schemas
# ============================================================================


class GetInput(BaseModel):
    """Input schema for vector.get tool."""

    ids: List[str] = Field(
        ...,
        description="List of chunk IDs to retrieve",
        min_length=1,
    )


class GetItem(BaseModel):
    """A single item from vector.get."""

    id: str = Field(
        ...,
        description="Chunk identifier",
    )
    text: str = Field(
        ...,
        description="Chunk content",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Chunk metadata",
    )


class GetOutput(BaseModel):
    """Output schema for vector.get tool."""

    items: List[GetItem] = Field(
        default_factory=list,
        description="Retrieved chunks",
    )


# ============================================================================
# vector.delete schemas
# ============================================================================


class DeleteWhere(BaseModel):
    """Filter conditions for vector.delete."""

    doc_id: Optional[str] = Field(
        None,
        description="Delete all chunks for a document",
    )
    path_prefix: Optional[str] = Field(
        None,
        description="Delete chunks with paths starting with this prefix",
    )
    library_id: Optional[str] = Field(
        None,
        description="Delete all chunks in a library",
    )


class DeleteInput(BaseModel):
    """Input schema for vector.delete tool."""

    where: DeleteWhere = Field(
        ...,
        description="Filter conditions for deletion (at least one field required)",
    )


class DeleteOutput(BaseModel):
    """Output schema for vector.delete tool."""

    deleted_count: int = Field(
        ...,
        description="Number of chunks deleted",
    )
