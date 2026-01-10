"""Semantic search service using ChromaDB and Ollama embeddings."""

import uuid
from typing import Any, Dict, List, Optional

import httpx
import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.file import FileMetadata
from app.models.library import Library

logger = structlog.get_logger(__name__)


class OllamaEmbeddingService:
    """Service for generating embeddings using Ollama."""

    def __init__(
        self,
        base_url: str = None,
        model: str = None,
    ):
        self.base_url = base_url or settings.ollama_url
        self.model = model or settings.ollama_embedding_model

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [])
            except Exception as e:
                logger.error("ollama_embedding_error", error=str(e))
                raise

    async def generate_embeddings_batch(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings


class ChromaDBService:
    """Service for vector storage and search using ChromaDB."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
    ):
        self.host = host or settings.chromadb_host
        self.port = port or settings.chromadb_port
        self.base_url = f"http://{self.host}:{self.port}"
        self._collection_cache: Dict[str, str] = {}

    async def _get_or_create_collection(
        self,
        library_id: uuid.UUID,
    ) -> str:
        """Get or create a collection for a library."""
        collection_name = f"beacon_lib_{str(library_id).replace('-', '_')}"

        if collection_name in self._collection_cache:
            return collection_name

        async with httpx.AsyncClient() as client:
            # Try to get existing collection
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/collections/{collection_name}",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    self._collection_cache[collection_name] = collection_name
                    return collection_name
            except Exception:
                pass

            # Create new collection
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/collections",
                    json={
                        "name": collection_name,
                        "metadata": {"library_id": str(library_id)},
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                self._collection_cache[collection_name] = collection_name
                return collection_name
            except Exception as e:
                logger.error(
                    "chromadb_create_collection_error",
                    collection=collection_name,
                    error=str(e),
                )
                raise

    async def add_document(
        self,
        library_id: uuid.UUID,
        document_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a document to the vector store."""
        collection_name = await self._get_or_create_collection(library_id)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/collections/{collection_name}/add",
                    json={
                        "ids": [document_id],
                        "embeddings": [embedding],
                        "documents": [content],
                        "metadatas": [metadata or {}],
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(
                    "chromadb_add_document_error",
                    document_id=document_id,
                    error=str(e),
                )
                return False

    async def update_document(
        self,
        library_id: uuid.UUID,
        document_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update a document in the vector store."""
        collection_name = await self._get_or_create_collection(library_id)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/collections/{collection_name}/update",
                    json={
                        "ids": [document_id],
                        "embeddings": [embedding],
                        "documents": [content],
                        "metadatas": [metadata or {}],
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(
                    "chromadb_update_document_error",
                    document_id=document_id,
                    error=str(e),
                )
                return False

    async def delete_document(
        self,
        library_id: uuid.UUID,
        document_id: str,
    ) -> bool:
        """Delete a document from the vector store."""
        collection_name = await self._get_or_create_collection(library_id)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/collections/{collection_name}/delete",
                    json={"ids": [document_id]},
                    timeout=10.0,
                )
                response.raise_for_status()
                return True
            except Exception as e:
                logger.error(
                    "chromadb_delete_document_error",
                    document_id=document_id,
                    error=str(e),
                )
                return False

    async def search(
        self,
        library_id: uuid.UUID,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents."""
        collection_name = await self._get_or_create_collection(library_id)

        async with httpx.AsyncClient() as client:
            try:
                body = {
                    "query_embeddings": [query_embedding],
                    "n_results": n_results,
                    "include": ["documents", "metadatas", "distances"],
                }
                if where:
                    body["where"] = where

                response = await client.post(
                    f"{self.base_url}/api/v1/collections/{collection_name}/query",
                    json=body,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                # Parse results
                results = []
                if data.get("ids") and data["ids"][0]:
                    for i, doc_id in enumerate(data["ids"][0]):
                        results.append({
                            "id": doc_id,
                            "document": data["documents"][0][i] if data.get("documents") else None,
                            "metadata": data["metadatas"][0][i] if data.get("metadatas") else {},
                            "distance": data["distances"][0][i] if data.get("distances") else 0,
                        })

                return results
            except Exception as e:
                logger.error(
                    "chromadb_search_error",
                    library_id=str(library_id),
                    error=str(e),
                )
                return []


class SemanticSearchService:
    """High-level semantic search service."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[OllamaEmbeddingService] = None,
        vector_store: Optional[ChromaDBService] = None,
    ):
        self.db = db
        self.embedding_service = embedding_service or OllamaEmbeddingService()
        self.vector_store = vector_store or ChromaDBService()

    async def index_file(
        self,
        file_id: uuid.UUID,
        content: str,
    ) -> bool:
        """Index a file for semantic search."""
        # Get file metadata
        query = select(FileMetadata).where(FileMetadata.id == file_id)
        result = await self.db.execute(query)
        file = result.scalar_one_or_none()

        if not file:
            return False

        # Generate embedding
        try:
            # Truncate content if too long
            max_content_length = 8000
            truncated_content = content[:max_content_length]

            embedding = await self.embedding_service.generate_embedding(truncated_content)
        except Exception as e:
            logger.error("index_file_embedding_error", file_id=str(file_id), error=str(e))
            return False

        # Store in vector database
        metadata = {
            "file_id": str(file.id),
            "file_name": file.name,
            "mime_type": file.mime_type,
            "path": file.path or "/",
            "library_id": str(file.library_id),
        }

        return await self.vector_store.add_document(
            library_id=file.library_id,
            document_id=str(file.id),
            content=truncated_content,
            embedding=embedding,
            metadata=metadata,
        )

    async def update_file_index(
        self,
        file_id: uuid.UUID,
        content: str,
    ) -> bool:
        """Update the index for a file."""
        # Get file metadata
        query = select(FileMetadata).where(FileMetadata.id == file_id)
        result = await self.db.execute(query)
        file = result.scalar_one_or_none()

        if not file:
            return False

        # Generate new embedding
        try:
            max_content_length = 8000
            truncated_content = content[:max_content_length]
            embedding = await self.embedding_service.generate_embedding(truncated_content)
        except Exception as e:
            logger.error("update_index_embedding_error", file_id=str(file_id), error=str(e))
            return False

        metadata = {
            "file_id": str(file.id),
            "file_name": file.name,
            "mime_type": file.mime_type,
            "path": file.path or "/",
            "library_id": str(file.library_id),
        }

        return await self.vector_store.update_document(
            library_id=file.library_id,
            document_id=str(file.id),
            content=truncated_content,
            embedding=embedding,
            metadata=metadata,
        )

    async def remove_file_index(
        self,
        file_id: uuid.UUID,
        library_id: uuid.UUID,
    ) -> bool:
        """Remove a file from the search index."""
        return await self.vector_store.delete_document(
            library_id=library_id,
            document_id=str(file_id),
        )

    async def search(
        self,
        query: str,
        library_id: Optional[uuid.UUID] = None,
        limit: int = 10,
        mime_type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for files using semantic similarity."""
        # Generate query embedding
        try:
            query_embedding = await self.embedding_service.generate_embedding(query)
        except Exception as e:
            logger.error("search_embedding_error", query=query, error=str(e))
            return []

        # Build where filter
        where = None
        if mime_type_filter:
            where = {"mime_type": mime_type_filter}

        # Search across libraries
        if library_id:
            # Search single library
            results = await self.vector_store.search(
                library_id=library_id,
                query_embedding=query_embedding,
                n_results=limit,
                where=where,
            )
        else:
            # Search all libraries
            lib_query = select(Library).where(Library.is_deleted == False)
            lib_result = await self.db.execute(lib_query)
            libraries = lib_result.scalars().all()

            all_results = []
            for lib in libraries:
                lib_results = await self.vector_store.search(
                    library_id=lib.id,
                    query_embedding=query_embedding,
                    n_results=limit,
                    where=where,
                )
                all_results.extend(lib_results)

            # Sort by distance and limit
            all_results.sort(key=lambda x: x.get("distance", float("inf")))
            results = all_results[:limit]

        # Enrich results with file metadata
        enriched_results = []
        for result in results:
            file_id = result.get("metadata", {}).get("file_id")
            if file_id:
                file_query = select(FileMetadata).where(
                    and_(
                        FileMetadata.id == uuid.UUID(file_id),
                        FileMetadata.is_deleted == False,
                    )
                )
                file_result = await self.db.execute(file_query)
                file = file_result.scalar_one_or_none()

                if file:
                    enriched_results.append({
                        "file_id": str(file.id),
                        "file_name": file.name,
                        "library_id": str(file.library_id),
                        "path": file.path,
                        "mime_type": file.mime_type,
                        "size": file.size,
                        "relevance_score": 1 - result.get("distance", 0),  # Convert distance to score
                        "snippet": result.get("document", "")[:200],
                    })

        return enriched_results
