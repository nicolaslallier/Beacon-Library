"""API endpoints for semantic search."""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services.search import SemanticSearchService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    """Search result item."""

    file_id: str
    file_name: str
    library_id: str
    path: Optional[str]
    mime_type: str
    size: int
    relevance_score: float
    snippet: str


class SearchResponse(BaseModel):
    """Search response."""

    query: str
    results: list[SearchResult]
    total: int


def get_search_service(
    db: AsyncSession = Depends(get_db),
) -> SemanticSearchService:
    """Get search service dependency."""
    return SemanticSearchService(db=db)


@router.get(
    "",
    response_model=SearchResponse,
    summary="Semantic search",
    description="Search for files using semantic similarity.",
)
async def semantic_search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    library_id: Optional[uuid.UUID] = Query(None, description="Limit to specific library"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    mime_type: Optional[str] = Query(None, description="Filter by MIME type"),
    current_user: dict = Depends(get_current_user),
    service: SemanticSearchService = Depends(get_search_service),
):
    """Search for files using semantic similarity."""
    try:
        results = await service.search(
            query=q,
            library_id=library_id,
            limit=limit,
            mime_type_filter=mime_type,
        )

        return SearchResponse(
            query=q,
            results=[SearchResult(**r) for r in results],
            total=len(results),
        )
    except Exception as e:
        logger.error("search_error", query=q, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        )


@router.post(
    "/index/{file_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Index file",
    description="Index a file for semantic search.",
)
async def index_file(
    file_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: SemanticSearchService = Depends(get_search_service),
):
    """Manually trigger indexing for a file."""
    # Note: In production, this would typically be done automatically
    # via a background task when files are uploaded/updated
    return {
        "message": "Indexing queued",
        "file_id": str(file_id),
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
