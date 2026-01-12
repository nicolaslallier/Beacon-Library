"""Semantic search service using ChromaDB and Ollama embeddings.

Enhanced with:
- Multi-chunk indexing for large files
- AST-based code chunking
- Rich metadata extraction
- Language and chunk type filtering
"""

import asyncio
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

# Background indexing queue
_indexing_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
_indexing_task: Optional[asyncio.Task] = None


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
        import chromadb

        self.host = host or settings.chromadb_host
        self.port = port or settings.chromadb_port
        # Use the official ChromaDB client
        self._client = chromadb.HttpClient(host=self.host, port=self.port)
        self._collection_cache: Dict[str, Any] = {}

    @staticmethod
    def _collection_name(library_id: uuid.UUID) -> str:
        return f"beacon_lib_{str(library_id).replace('-', '_')}"

    def _get_or_create_collection(self, library_id: uuid.UUID):
        """Get or create a collection for a library."""
        collection_name = self._collection_name(library_id)

        if collection_name in self._collection_cache:
            return self._collection_cache[collection_name]

        try:
            collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"library_id": str(library_id)},
            )
            self._collection_cache[collection_name] = collection
            return collection
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
        try:
            collection = self._get_or_create_collection(library_id)
            collection.add(
                ids=[document_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[metadata or {}],
            )
            return True
        except Exception as e:
            logger.error(
                "chromadb_add_document_error",
                document_id=document_id,
                error=str(e),
            )
            return False

    async def add_documents_batch(
        self,
        library_id: uuid.UUID,
        document_ids: List[str],
        contents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> bool:
        """Add multiple documents to the vector store in batch."""
        try:
            collection = self._get_or_create_collection(library_id)
            collection.add(
                ids=document_ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas,
            )
            return True
        except Exception as e:
            logger.error(
                "chromadb_add_documents_batch_error",
                count=len(document_ids),
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
        try:
            collection = self._get_or_create_collection(library_id)
            collection.update(
                ids=[document_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[metadata or {}],
            )
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
        try:
            collection = self._get_or_create_collection(library_id)
            collection.delete(ids=[document_id])
            return True
        except Exception as e:
            logger.error(
                "chromadb_delete_document_error",
                document_id=document_id,
                error=str(e),
            )
            return False

    async def delete_documents_by_file(
        self,
        library_id: uuid.UUID,
        file_id: str,
    ) -> bool:
        """Delete all chunks belonging to a file."""
        try:
            collection = self._get_or_create_collection(library_id)
            # Delete by metadata filter
            collection.delete(where={"file_id": file_id})
            return True
        except Exception as e:
            logger.error(
                "chromadb_delete_by_file_error",
                file_id=file_id,
                error=str(e),
            )
            return False

    async def delete_library_collection(self, library_id: uuid.UUID) -> bool:
        """Delete the entire collection for a library.

        This removes all embeddings for that library.
        """
        collection_name = self._collection_name(library_id)
        try:
            # Chroma client API differs slightly across versions.
            try:
                self._client.delete_collection(name=collection_name)
            except TypeError:
                self._client.delete_collection(collection_name)

            self._collection_cache.pop(collection_name, None)
            return True
        except Exception as e:
            logger.error(
                "chromadb_delete_collection_error",
                collection=collection_name,
                library_id=str(library_id),
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
        try:
            collection = self._get_or_create_collection(library_id)
            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                query_params["where"] = where

            data = collection.query(**query_params)

            # Parse results
            results = []
            if data.get("ids") and data["ids"][0]:
                for i, doc_id in enumerate(data["ids"][0]):
                    results.append({
                        "id": doc_id,
                        "document": (
                            data["documents"][0][i]
                            if data.get("documents") else None
                        ),
                        "metadata": (
                            data["metadatas"][0][i]
                            if data.get("metadatas") else {}
                        ),
                        "distance": (
                            data["distances"][0][i]
                            if data.get("distances") else 0
                        ),
                    })

            return results
        except Exception as e:
            logger.error(
                "chromadb_search_error",
                library_id=str(library_id),
                error=str(e),
            )
            return []

    async def get_chunks_by_file(
        self,
        library_id: uuid.UUID,
        file_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all chunks for a specific file."""
        try:
            collection = self._get_or_create_collection(library_id)
            results = collection.get(
                where={"file_id": file_id},
                include=["documents", "metadatas"],
            )

            chunks = []
            if results.get("ids"):
                for i, chunk_id in enumerate(results["ids"]):
                    chunks.append({
                        "id": chunk_id,
                        "document": results["documents"][i] if results.get("documents") else None,
                        "metadata": results["metadatas"][i] if results.get("metadatas") else {},
                    })

            return chunks
        except Exception as e:
            logger.error(
                "chromadb_get_chunks_error",
                file_id=file_id,
                error=str(e),
            )
            return []


class SemanticSearchService:
    """High-level semantic search service with multi-chunk support."""

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
        """Index a file for semantic search (legacy single-chunk mode)."""
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
            "file_name": file.filename,
            "mime_type": file.content_type,
            "path": file.path or "/",
            "library_id": str(file.library_id),
            "chunk_type": "full",
            "chunk_index": 0,
        }

        return await self.vector_store.add_document(
            library_id=file.library_id,
            document_id=str(file.id),
            content=truncated_content,
            embedding=embedding,
            metadata=metadata,
        )

    async def index_file_chunked(
        self,
        file_id: uuid.UUID,
        content: str,
        file_name: str,
        mime_type: str,
    ) -> bool:
        """Index a file using smart chunking for better search.

        This method:
        1. Detects the file type and language
        2. Chunks the content appropriately (AST for code, sections for docs)
        3. Extracts rich metadata for each chunk
        4. Creates embeddings and stores in vector DB
        """
        from app.services.chunking import chunking_service
        from app.services.metadata_extraction import metadata_extraction_service

        # Get file metadata from DB
        query = select(FileMetadata).where(FileMetadata.id == file_id)
        result = await self.db.execute(query)
        file = result.scalar_one_or_none()

        if not file:
            logger.warning("index_file_chunked_not_found", file_id=str(file_id))
            return False

        # First, delete any existing chunks for this file
        await self.vector_store.delete_documents_by_file(
            library_id=file.library_id,
            file_id=str(file_id),
        )

        # Detect language and extract file-level metadata
        language = chunking_service.detect_language(file_name, content)

        # Extract metadata based on file type
        if chunking_service.is_code_file(language):
            file_metadata = metadata_extraction_service.extract_code_metadata(
                content, file_name, language
            )
            file_meta_dict = file_metadata.to_dict()
        else:
            file_metadata = metadata_extraction_service.extract_document_metadata(
                content, file_name
            )
            file_meta_dict = file_metadata.to_dict()

        # Chunk the content
        chunks = chunking_service.chunk_content(content, file_name, mime_type)

        if not chunks:
            # Fall back to single-chunk indexing
            logger.info(
                "index_file_chunked_fallback",
                file_id=str(file_id),
                reason="no_chunks_produced",
            )
            return await self.index_file(file_id, content)

        logger.info(
            "index_file_chunked_start",
            file_id=str(file_id),
            file_name=file_name,
            language=language.value,
            chunk_count=len(chunks),
        )

        # Prepare batch data
        document_ids = []
        contents = []
        embeddings = []
        metadatas = []

        for chunk in chunks:
            chunk_id = f"{file_id}:chunk:{chunk.index}"
            document_ids.append(chunk_id)
            contents.append(chunk.content)

            # Generate embedding for this chunk
            try:
                # Truncate chunk content for embedding
                chunk_text = chunk.content[:8000]
                embedding = await self.embedding_service.generate_embedding(chunk_text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(
                    "chunk_embedding_error",
                    file_id=str(file_id),
                    chunk_index=chunk.index,
                    error=str(e),
                )
                continue

            # Build chunk metadata
            chunk_metadata = {
                # File identification
                "file_id": str(file.id),
                "file_name": file.filename,
                "mime_type": file.content_type,
                "path": file.path or "/",
                "library_id": str(file.library_id),
                # Chunk info
                "chunk_index": chunk.index,
                "chunk_type": chunk.chunk_type.value,
                "language": chunk.language.value,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
            }

            # Add optional chunk-specific metadata
            if chunk.name:
                chunk_metadata["name"] = chunk.name
            if chunk.parent_name:
                chunk_metadata["parent_name"] = chunk.parent_name
            if chunk.docstring:
                chunk_metadata["docstring"] = chunk.docstring[:500]
            if chunk.imports:
                chunk_metadata["imports"] = ",".join(chunk.imports[:20])
            if chunk.heading:
                chunk_metadata["heading"] = chunk.heading
            if chunk.heading_level:
                chunk_metadata["heading_level"] = chunk.heading_level
            if chunk.parent_heading:
                chunk_metadata["parent_heading"] = chunk.parent_heading
            if chunk.has_code_blocks:
                chunk_metadata["has_code_blocks"] = True
            if chunk.code_languages:
                chunk_metadata["code_languages"] = ",".join(chunk.code_languages)

            # Add file-level metadata (for filtering)
            if "frameworks" in file_meta_dict and file_meta_dict["frameworks"]:
                chunk_metadata["frameworks"] = file_meta_dict["frameworks"]
            if "has_tests" in file_meta_dict:
                chunk_metadata["has_tests"] = file_meta_dict["has_tests"]

            metadatas.append(chunk_metadata)

        # Store all chunks in batch
        if document_ids:
            success = await self.vector_store.add_documents_batch(
                library_id=file.library_id,
                document_ids=document_ids,
                contents=contents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            if success:
                logger.info(
                    "index_file_chunked_complete",
                    file_id=str(file_id),
                    chunk_count=len(document_ids),
                )
            else:
                logger.warning(
                    "index_file_chunked_failed",
                    file_id=str(file_id),
                )

            return success

        return False

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
            "file_name": file.filename,
            "mime_type": file.content_type,
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

    async def update_file_index_chunked(
        self,
        file_id: uuid.UUID,
        content: str,
        file_name: str,
        mime_type: str,
    ) -> bool:
        """Update file index using chunked approach.

        This deletes existing chunks and re-indexes.
        """
        return await self.index_file_chunked(
            file_id=file_id,
            content=content,
            file_name=file_name,
            mime_type=mime_type,
        )

    async def remove_file_index(
        self,
        file_id: uuid.UUID,
        library_id: uuid.UUID,
    ) -> bool:
        """Remove a file from the search index (all chunks)."""
        # Try to delete by file metadata filter (for chunked files)
        success = await self.vector_store.delete_documents_by_file(
            library_id=library_id,
            file_id=str(file_id),
        )

        # Also try to delete by direct ID (for legacy single-chunk files)
        await self.vector_store.delete_document(
            library_id=library_id,
            document_id=str(file_id),
        )

        return success

    async def search(
        self,
        query: str,
        library_id: Optional[uuid.UUID] = None,
        limit: int = 10,
        mime_type_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        chunk_type_filter: Optional[str] = None,
        include_context: bool = False,
        group_by_file: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search for files using semantic similarity.

        Args:
            query: Search query text
            library_id: Optional library to search within
            limit: Maximum number of results
            mime_type_filter: Filter by MIME type
            language_filter: Filter by programming language
            chunk_type_filter: Filter by chunk type (function, class, section, etc.)
            include_context: Include surrounding chunks in results
            group_by_file: Group results by file

        Returns:
            List of search results with metadata
        """
        # Generate query embedding
        try:
            query_embedding = await self.embedding_service.generate_embedding(query)
        except Exception as e:
            logger.error("search_embedding_error", query=query, error=str(e))
            return []

        # Build where filter
        where = {}
        if mime_type_filter:
            where["mime_type"] = mime_type_filter
        if language_filter:
            where["language"] = language_filter
        if chunk_type_filter:
            where["chunk_type"] = chunk_type_filter

        where_clause = where if where else None

        # Search across libraries
        if library_id:
            # Search single library
            results = await self.vector_store.search(
                library_id=library_id,
                query_embedding=query_embedding,
                n_results=limit * 2 if group_by_file else limit,  # Fetch more for grouping
                where=where_clause,
            )
        else:
            # Search all libraries
            lib_query = select(Library).where(Library.is_deleted.is_(False))
            lib_result = await self.db.execute(lib_query)
            libraries = lib_result.scalars().all()

            all_results = []
            for lib in libraries:
                lib_results = await self.vector_store.search(
                    library_id=lib.id,
                    query_embedding=query_embedding,
                    n_results=limit,
                    where=where_clause,
                )
                all_results.extend(lib_results)

            # Sort by distance and limit
            all_results.sort(key=lambda x: x.get("distance", float("inf")))
            results = all_results[:limit * 2 if group_by_file else limit]

        # Enrich results with file metadata
        enriched_results = []
        seen_files = set()

        for result in results:
            metadata = result.get("metadata", {})
            file_id = metadata.get("file_id")

            if not file_id:
                continue

            # For group_by_file, skip if we've already included this file
            if group_by_file and file_id in seen_files:
                continue

            # Get file from database
            file_query = select(FileMetadata).where(
                and_(
                    FileMetadata.id == uuid.UUID(file_id),
                    FileMetadata.is_deleted.is_(False),
                )
            )
            file_result = await self.db.execute(file_query)
            file = file_result.scalar_one_or_none()

            if not file:
                continue

            seen_files.add(file_id)
            distance = result.get("distance", 0)

            enriched_result = {
                "file_id": str(file.id),
                "file_name": file.filename,
                "library_id": str(file.library_id),
                "path": file.path,
                "mime_type": file.content_type,
                "size": file.size_bytes,
                # Convert distance (0=best) to score (1=best)
                "relevance_score": max(0, 1 - distance),
                "snippet": result.get("document", "")[:300],
                # Chunk metadata
                "chunk_index": metadata.get("chunk_index", 0),
                "chunk_type": metadata.get("chunk_type", "full"),
                "language": metadata.get("language"),
                "name": metadata.get("name"),
                "line_start": metadata.get("line_start"),
                "line_end": metadata.get("line_end"),
            }

            # Add optional metadata
            if metadata.get("heading"):
                enriched_result["heading"] = metadata["heading"]
            if metadata.get("docstring"):
                enriched_result["docstring"] = metadata["docstring"]
            if metadata.get("imports"):
                enriched_result["imports"] = metadata["imports"].split(",")
            if metadata.get("frameworks"):
                enriched_result["frameworks"] = metadata["frameworks"].split(",")

            # Include context (surrounding chunks) if requested
            if include_context and not group_by_file:
                context = await self._get_surrounding_context(
                    library_id=uuid.UUID(metadata.get("library_id")),
                    file_id=file_id,
                    chunk_index=metadata.get("chunk_index", 0),
                )
                if context:
                    enriched_result["context"] = context

            enriched_results.append(enriched_result)

            if len(enriched_results) >= limit:
                break

        return enriched_results

    async def _get_surrounding_context(
        self,
        library_id: uuid.UUID,
        file_id: str,
        chunk_index: int,
        context_size: int = 1,
    ) -> List[Dict[str, Any]]:
        """Get surrounding chunks for context."""
        chunks = await self.vector_store.get_chunks_by_file(
            library_id=library_id,
            file_id=file_id,
        )

        if not chunks:
            return []

        # Sort by chunk index
        chunks.sort(key=lambda c: c.get("metadata", {}).get("chunk_index", 0))

        # Find surrounding chunks
        context = []
        for chunk in chunks:
            idx = chunk.get("metadata", {}).get("chunk_index", 0)
            if abs(idx - chunk_index) <= context_size and idx != chunk_index:
                context.append({
                    "chunk_index": idx,
                    "snippet": chunk.get("document", "")[:200],
                    "chunk_type": chunk.get("metadata", {}).get("chunk_type"),
                })

        return context


async def start_indexing_worker(db_session_factory, storage_service):
    """Start the background indexing worker."""
    global _indexing_task

    if _indexing_task is not None:
        return

    async def worker():
        from app.services.content_extraction import content_extraction_service

        while True:
            item = None
            try:
                # Get next item from queue
                item = await _indexing_queue.get()
            except asyncio.CancelledError:
                break

            try:
                file_id = item.get("file_id")
                library_id = item.get("library_id")
                action = item.get("action", "index")

                # Handle de-index requests without touching storage/DB.
                if action == "delete_file":
                    if file_id and library_id:
                        try:
                            vector_store = ChromaDBService()
                            # Delete all chunks for the file
                            await vector_store.delete_documents_by_file(
                                library_id=library_id,
                                file_id=str(file_id),
                            )
                            # Also try legacy single-doc delete
                            await vector_store.delete_document(
                                library_id=library_id,
                                document_id=str(file_id),
                            )
                            logger.info(
                                "deindex_file_complete",
                                file_id=str(file_id),
                                library_id=str(library_id),
                            )
                        except Exception as e:
                            logger.warning(
                                "deindex_file_failed",
                                file_id=str(file_id),
                                library_id=str(library_id),
                                error=str(e),
                            )
                    _indexing_queue.task_done()
                    continue

                if action == "delete_library":
                    if library_id:
                        try:
                            vector_store = ChromaDBService()
                            await vector_store.delete_library_collection(library_id)
                            logger.info(
                                "deindex_library_complete",
                                library_id=str(library_id),
                            )
                        except Exception as e:
                            logger.warning(
                                "deindex_library_failed",
                                library_id=str(library_id),
                                error=str(e),
                            )
                    _indexing_queue.task_done()
                    continue

                logger.info("indexing_file_start", file_id=str(file_id))

                async with db_session_factory() as db:
                    # Get file metadata
                    result = await db.execute(
                        select(FileMetadata).where(FileMetadata.id == file_id)
                    )
                    file = result.scalar_one_or_none()

                    if not file:
                        logger.warning(
                            "indexing_file_not_found", file_id=str(file_id)
                        )
                        _indexing_queue.task_done()
                        continue

                    # Get library for bucket name
                    lib_result = await db.execute(
                        select(Library).where(Library.id == file.library_id)
                    )
                    library = lib_result.scalar_one_or_none()

                    if not library:
                        _indexing_queue.task_done()
                        continue

                    # Check if content can be extracted
                    if not content_extraction_service.can_extract(file.content_type, file.filename):
                        # Still index with filename/metadata only
                        searchable_content = (
                            content_extraction_service.create_searchable_content(
                                file_name=file.filename,
                                file_path=file.path,
                                extracted_text=None,
                                mime_type=file.content_type,
                            )
                        )
                        extracted_text = None
                    else:
                        # Download file content for extraction
                        try:
                            file_content = await storage_service.download_file(
                                bucket=library.bucket_name,
                                key=file.storage_key,
                            )

                            # Extract text
                            extracted_text = (
                                await content_extraction_service.extract_text(
                                    file_content=file_content,
                                    file_name=file.filename,
                                    mime_type=file.content_type,
                                )
                            )

                            # Create searchable content
                            searchable_content = (
                                content_extraction_service.create_searchable_content(
                                    file_name=file.filename,
                                    file_path=file.path,
                                    extracted_text=extracted_text,
                                    mime_type=file.content_type,
                                )
                            )
                        except Exception as e:
                            logger.error(
                                "indexing_content_error",
                                file_id=str(file_id),
                                error=str(e),
                            )
                            # Fall back to metadata only
                            searchable_content = (
                                content_extraction_service.create_searchable_content(
                                    file_name=file.filename,
                                    file_path=file.path,
                                    extracted_text=None,
                                    mime_type=file.content_type,
                                )
                            )
                            extracted_text = None

                    # Index the content using chunked approach if enabled
                    search_service = SemanticSearchService(db=db)

                    if settings.enable_code_analysis and extracted_text:
                        # Use smart chunking for better search
                        success = await search_service.index_file_chunked(
                            file_id=file.id,
                            content=extracted_text,
                            file_name=file.filename,
                            mime_type=file.content_type,
                        )
                    else:
                        # Fall back to simple indexing
                        success = await search_service.index_file(
                            file_id=file.id,
                            content=searchable_content,
                        )

                    if success:
                        logger.info(
                            "indexing_file_complete",
                            file_id=str(file_id),
                            filename=file.filename,
                        )
                    else:
                        logger.warning(
                            "indexing_file_failed",
                            file_id=str(file_id),
                        )

                _indexing_queue.task_done()

            except asyncio.CancelledError:
                # Mark task done before exiting
                if item is not None:
                    _indexing_queue.task_done()
                break
            except Exception as e:
                logger.error("indexing_worker_error", error=str(e))
                _indexing_queue.task_done()
                await asyncio.sleep(1)  # Prevent tight loop on errors

    _indexing_task = asyncio.create_task(worker())
    logger.info("indexing_worker_started")


async def queue_file_for_indexing(file_id: uuid.UUID, library_id: uuid.UUID):
    """Queue a file for background indexing."""
    try:
        _indexing_queue.put_nowait({
            "action": "index",
            "file_id": file_id,
            "library_id": library_id,
        })
        logger.debug("file_queued_for_indexing", file_id=str(file_id))
    except asyncio.QueueFull:
        logger.warning(
            "indexing_queue_full",
            file_id=str(file_id),
            message="File will not be indexed",
        )


async def queue_file_for_deindexing(file_id: uuid.UUID, library_id: uuid.UUID):
    """Queue a file for removal from the vector index."""
    try:
        _indexing_queue.put_nowait({
            "action": "delete_file",
            "file_id": file_id,
            "library_id": library_id,
        })
        logger.debug("file_queued_for_deindexing", file_id=str(file_id))
    except asyncio.QueueFull:
        logger.warning(
            "indexing_queue_full",
            file_id=str(file_id),
            message="File will not be de-indexed",
        )


async def queue_library_for_deindexing(library_id: uuid.UUID):
    """Queue a library collection for deletion from the vector index."""
    try:
        _indexing_queue.put_nowait({
            "action": "delete_library",
            "library_id": library_id,
        })
        logger.debug(
            "library_queued_for_deindexing",
            library_id=str(library_id),
        )
    except asyncio.QueueFull:
        logger.warning(
            "indexing_queue_full",
            library_id=str(library_id),
            message="Library will not be de-indexed",
        )


async def stop_indexing_worker():
    """Stop the background indexing worker."""
    global _indexing_task

    if _indexing_task:
        _indexing_task.cancel()
        try:
            await _indexing_task
        except asyncio.CancelledError:
            pass
        _indexing_task = None
        logger.info("indexing_worker_stopped")
