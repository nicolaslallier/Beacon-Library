"""API endpoints for semantic search.

Enhanced with:
- Language and chunk type filtering
- Context inclusion option
- File grouping option
- Rich metadata in results
"""

import uuid
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import FileMetadata
from app.services.search import SemanticSearchService, queue_file_for_indexing

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


class ChunkContext(BaseModel):
    """Context chunk information."""

    chunk_index: int
    snippet: str
    chunk_type: Optional[str] = None


class SearchResult(BaseModel):
    """Search result item with enhanced metadata."""

    file_id: str
    file_name: str
    library_id: str
    path: Optional[str] = None
    mime_type: str
    size: int
    relevance_score: float
    snippet: str

    # Chunk metadata
    chunk_index: int = 0
    chunk_type: str = "full"
    language: Optional[str] = None
    name: Optional[str] = Field(None, description="Function/class/section name")
    line_start: Optional[int] = None
    line_end: Optional[int] = None

    # Optional enriched metadata
    heading: Optional[str] = Field(None, description="Section heading for docs")
    docstring: Optional[str] = Field(None, description="Docstring for code")
    imports: Optional[List[str]] = Field(None, description="Import statements")
    frameworks: Optional[List[str]] = Field(None, description="Detected frameworks")

    # Context (surrounding chunks)
    context: Optional[List[ChunkContext]] = Field(
        None, description="Surrounding chunks for context"
    )


class SearchResponse(BaseModel):
    """Search response."""

    query: str
    results: List[SearchResult]
    total: int
    filters_applied: dict = Field(default_factory=dict)


class IndexStatusResponse(BaseModel):
    """Index status response."""

    file_id: str
    indexed: bool
    chunk_count: int = 0
    language: Optional[str] = None


def get_search_service(
    db: AsyncSession = Depends(get_db),
) -> SemanticSearchService:
    """Get search service dependency."""
    return SemanticSearchService(db=db)


@router.get(
    "",
    response_model=SearchResponse,
    summary="Semantic search",
    description="""Search for files using semantic similarity.

    Supports filtering by:
    - `mime_type`: Filter by MIME type (e.g., "text/python", "application/pdf")
    - `language`: Filter by programming language (e.g., "python", "typescript")
    - `chunk_type`: Filter by chunk type (e.g., "function", "class", "section")

    Options:
    - `include_context`: Include surrounding chunks in results
    - `group_by_file`: Return one result per file (best matching chunk)
    """,
)
async def semantic_search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    library_id: Optional[uuid.UUID] = Query(None, description="Limit to specific library"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    mime_type: Optional[str] = Query(None, description="Filter by MIME type"),
    language: Optional[str] = Query(
        None,
        description="Filter by programming language (python, typescript, go, etc.)",
    ),
    chunk_type: Optional[str] = Query(
        None,
        description="Filter by chunk type (function, class, method, section, etc.)",
    ),
    include_context: bool = Query(
        False,
        description="Include surrounding chunks in results",
    ),
    group_by_file: bool = Query(
        False,
        description="Group results by file (return best match per file)",
    ),
    current_user: dict = Depends(get_current_user),
    service: SemanticSearchService = Depends(get_search_service),
):
    """Search for files using semantic similarity with enhanced filtering."""
    try:
        results = await service.search(
            query=q,
            library_id=library_id,
            limit=limit,
            mime_type_filter=mime_type,
            language_filter=language,
            chunk_type_filter=chunk_type,
            include_context=include_context,
            group_by_file=group_by_file,
        )

        # Build filters applied dict
        filters_applied = {}
        if library_id:
            filters_applied["library_id"] = str(library_id)
        if mime_type:
            filters_applied["mime_type"] = mime_type
        if language:
            filters_applied["language"] = language
        if chunk_type:
            filters_applied["chunk_type"] = chunk_type
        if include_context:
            filters_applied["include_context"] = True
        if group_by_file:
            filters_applied["group_by_file"] = True

        # Convert results to response model
        search_results = []
        for r in results:
            # Handle context if present
            context = None
            if r.get("context"):
                context = [ChunkContext(**c) for c in r["context"]]

            search_results.append(
                SearchResult(
                    file_id=r["file_id"],
                    file_name=r["file_name"],
                    library_id=r["library_id"],
                    path=r.get("path"),
                    mime_type=r["mime_type"],
                    size=r["size"],
                    relevance_score=r["relevance_score"],
                    snippet=r["snippet"],
                    chunk_index=r.get("chunk_index", 0),
                    chunk_type=r.get("chunk_type", "full"),
                    language=r.get("language"),
                    name=r.get("name"),
                    line_start=r.get("line_start"),
                    line_end=r.get("line_end"),
                    heading=r.get("heading"),
                    docstring=r.get("docstring"),
                    imports=r.get("imports"),
                    frameworks=r.get("frameworks"),
                    context=context,
                )
            )

        return SearchResponse(
            query=q,
            results=search_results,
            total=len(search_results),
            filters_applied=filters_applied,
        )
    except Exception as e:
        logger.error("search_error", query=q, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        )


@router.get(
    "/languages",
    summary="List supported languages",
    description="Get list of supported programming languages for filtering.",
)
async def list_supported_languages():
    """Return list of supported programming languages."""
    from app.services.chunking import Language

    return {
        "languages": [lang.value for lang in Language if lang != Language.UNKNOWN],
        "code_languages": [
            "python",
            "javascript",
            "typescript",
            "go",
            "rust",
            "java",
            "c",
            "cpp",
            "csharp",
            "ruby",
            "php",
            "swift",
            "kotlin",
            "scala",
            "shell",
            "sql",
        ],
        "doc_languages": [
            "markdown",
            "html",
            "plaintext",
        ],
        "config_languages": [
            "yaml",
            "json",
            "toml",
            "xml",
        ],
    }


@router.get(
    "/chunk-types",
    summary="List chunk types",
    description="Get list of chunk types for filtering.",
)
async def list_chunk_types():
    """Return list of chunk types."""
    from app.services.chunking import ChunkType

    return {
        "chunk_types": [ct.value for ct in ChunkType],
        "code_chunk_types": ["function", "class", "method", "module", "import"],
        "doc_chunk_types": ["section", "paragraph", "code_block"],
    }


@router.post(
    "/index/{file_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Index file",
    description="Queue a file for semantic search indexing.",
)
async def index_file(
    file_id: uuid.UUID,
    chunked: bool = Query(
        True, description="Use smart chunking for indexing"
    ),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger indexing for a file."""
    # Verify file exists
    result = await db.execute(
        select(FileMetadata).where(FileMetadata.id == file_id)
    )
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    await queue_file_for_indexing(file.id, file.library_id)

    return {
        "message": "Indexing queued",
        "file_id": str(file_id),
        "chunked": chunked,
    }


@router.delete(
    "/index/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove from index",
    description="Remove a file from the search index.",
)
async def remove_from_index(
    file_id: uuid.UUID,
    library_id: uuid.UUID = Query(..., description="Library ID"),
    current_user: dict = Depends(get_current_user),
    service: SemanticSearchService = Depends(get_search_service),
):
    """Remove a file from the search index."""
    await service.remove_file_index(file_id=file_id, library_id=library_id)


@router.post(
    "/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reindex files",
    description="Queue files for re-indexing. This is a background operation.",
)
async def reindex_files(
    library_id: Optional[uuid.UUID] = Query(None, description="Limit to specific library"),
    language: Optional[str] = Query(None, description="Only reindex files of this language"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue files for re-indexing in the background."""
    # Build query
    query = select(FileMetadata).where(FileMetadata.is_deleted.is_(False))

    if library_id:
        query = query.where(FileMetadata.library_id == library_id)

    result = await db.execute(query)
    files = result.scalars().all()

    # Filter by language if specified
    if language:
        from app.services.chunking import chunking_service

        filtered_files = []
        for file in files:
            detected_lang = chunking_service.detect_language(file.filename)
            if detected_lang.value == language:
                filtered_files.append(file)
        files = filtered_files

    queued_count = 0
    for file in files:
        await queue_file_for_indexing(file.id, file.library_id)
        queued_count += 1

    logger.info(
        "reindex_queued",
        count=queued_count,
        library_id=str(library_id) if library_id else "all",
        language=language,
    )

    return {
        "message": f"Queued {queued_count} files for re-indexing",
        "queued_count": queued_count,
        "filters": {
            "library_id": str(library_id) if library_id else None,
            "language": language,
        },
    }


@router.get(
    "/stats",
    summary="Search index statistics",
    description="Get statistics about the search index.",
)
async def get_index_stats(
    library_id: Optional[uuid.UUID] = Query(None, description="Specific library"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get search index statistics."""
    # Count files
    query = select(FileMetadata).where(FileMetadata.is_deleted.is_(False))
    if library_id:
        query = query.where(FileMetadata.library_id == library_id)

    result = await db.execute(query)
    files = result.scalars().all()

    # Count by language
    from app.services.chunking import chunking_service

    language_counts = {}
    for file in files:
        lang = chunking_service.detect_language(file.filename)
        lang_name = lang.value
        language_counts[lang_name] = language_counts.get(lang_name, 0) + 1

    return {
        "total_files": len(files),
        "by_language": language_counts,
        "library_id": str(library_id) if library_id else None,
    }
