"""MCP tool implementations for vector operations."""

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, List

import structlog

from app.config import settings
from app.schemas.vector import (
    DeleteInput,
    DeleteOutput,
    GetInput,
    GetOutput,
    GetItem,
    QueryInput,
    QueryOutput,
    QueryResult,
    QueryResultMetadata,
    UpsertInput,
    UpsertOutput,
    UpsertError,
)
from app.services.chroma import ChromaDBService
from app.services.embeddings import OllamaEmbeddingService

if TYPE_CHECKING:
    from app.mcp.server import MCPVectorServer

logger = structlog.get_logger(__name__)


def register_tools(server: "MCPVectorServer"):
    """Register all vector tools with the server."""

    chroma_service = ChromaDBService()
    embedding_service = OllamaEmbeddingService()

    # =========================================================================
    # vector.query
    # =========================================================================

    async def vector_query(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Semantic search by similarity.

        FR-01: Provide vector similarity search on text input
        FR-02: Return text, score, path, chunk_id
        FR-03: Support metadata filters
        """
        start_time = time.time()
        query_id = str(uuid.uuid4())

        try:
            # Parse and validate input
            input_data = QueryInput(**arguments)

            # Get agent ID from server context
            agent_id = server.current_agent_id or "anonymous"

            # Build ChromaDB where filter
            where_filter = {}

            if input_data.filters:
                filters = input_data.filters

                # Path filter (exact match or prefix handled differently)
                if filters.path:
                    where_filter["path"] = filters.path

                # Document ID filter
                if filters.doc_id:
                    where_filter["doc_id"] = filters.doc_id

                # MIME type filter
                if filters.doc_type:
                    where_filter["mime_type"] = filters.doc_type

                # Language filter
                if filters.language:
                    where_filter["language"] = filters.language

                # Chunk type filter
                if filters.chunk_type:
                    where_filter["chunk_type"] = filters.chunk_type

            # Determine which libraries to search
            library_ids = []

            if input_data.filters and input_data.filters.library_id:
                # Single library specified
                lib_id = uuid.UUID(input_data.filters.library_id)

                # Check access
                if not await server.access_service.check_library_access(
                    library_id=lib_id,
                    agent_id=agent_id,
                    for_write=False,
                ):
                    return QueryOutput(
                        results=[],
                        low_confidence=True,
                        query_id=query_id,
                    ).model_dump()

                library_ids = [lib_id]
            else:
                # Search all accessible libraries
                library_ids = await server.access_service.get_accessible_libraries(
                    agent_id=agent_id,
                    for_write=False,
                )

            if not library_ids:
                return QueryOutput(
                    results=[],
                    low_confidence=True,
                    query_id=query_id,
                ).model_dump()

            # Generate query embedding
            try:
                query_embedding = await embedding_service.generate_embedding(
                    input_data.text
                )
            except Exception as e:
                logger.error(
                    "query_embedding_error",
                    query_id=query_id,
                    error=str(e),
                )
                return QueryOutput(
                    results=[],
                    low_confidence=True,
                    query_id=query_id,
                ).model_dump()

            # Search across libraries
            all_results = []

            for lib_id in library_ids:
                lib_results = await chroma_service.search(
                    library_id=lib_id,
                    query_embedding=query_embedding,
                    n_results=input_data.top_k,
                    where=where_filter if where_filter else None,
                )
                all_results.extend(lib_results)

            # Sort by score (descending) and limit
            all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            all_results = all_results[: input_data.top_k]

            # Check if all results are low confidence
            low_confidence = all(
                r.get("score", 0) < settings.low_confidence_threshold
                for r in all_results
            ) if all_results else True

            # Convert to output format
            results = []
            for r in all_results:
                metadata = r.get("metadata", {})

                result = QueryResult(
                    id=r.get("id", ""),
                    text=r.get("text", ""),
                    score=r.get("score", 0),
                    metadata=QueryResultMetadata(
                        path=metadata.get("path", ""),
                        chunk_id=metadata.get("chunk_index", metadata.get("chunk_id", 0)),
                        doc_id=metadata.get("doc_id") or metadata.get("file_id"),
                        library_id=metadata.get("library_id"),
                        line_start=metadata.get("line_start"),
                        line_end=metadata.get("line_end"),
                        page=metadata.get("page"),
                        offset_start=metadata.get("offset_start"),
                        offset_end=metadata.get("offset_end"),
                        language=metadata.get("language"),
                        chunk_type=metadata.get("chunk_type"),
                        name=metadata.get("name"),
                        heading=metadata.get("heading"),
                        file_name=metadata.get("file_name"),
                    ),
                )
                results.append(result)

            # Log metrics
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "vector_query_complete",
                query_id=query_id,
                agent_id=agent_id,
                result_count=len(results),
                top_k=input_data.top_k,
                low_confidence=low_confidence,
                duration_ms=round(duration_ms, 2),
            )

            # Update metrics
            server.metrics["query_count"] += 1
            server.metrics["query_latency_sum"] += duration_ms
            if not results:
                server.metrics["no_results_count"] += 1
            if low_confidence:
                server.metrics["low_confidence_count"] += 1

            return QueryOutput(
                results=results,
                low_confidence=low_confidence,
                query_id=query_id,
            ).model_dump()

        except Exception as e:
            logger.error(
                "vector_query_error",
                query_id=query_id,
                error=str(e),
            )
            server.metrics["error_count"] += 1
            return QueryOutput(
                results=[],
                low_confidence=True,
                query_id=query_id,
            ).model_dump()

    # =========================================================================
    # vector.upsert_documents
    # =========================================================================

    async def vector_upsert_documents(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update chunks in Chroma.

        FR-04: Support upsert operations for chunks
        FR-05: Guarantee idempotence using doc_id + chunk_id
        """
        start_time = time.time()

        try:
            # Parse and validate input
            input_data = UpsertInput(**arguments)

            # Validate alignment
            if len(input_data.chunks) != len(input_data.metadata):
                return UpsertOutput(
                    upserted_count=0,
                    ids=[],
                    errors=[UpsertError(
                        index=0,
                        error="chunks and metadata arrays must have the same length",
                    )],
                ).model_dump()

            agent_id = server.current_agent_id or "anonymous"

            # Group chunks by library
            chunks_by_library: Dict[str, List[tuple]] = {}
            errors = []

            for i, (chunk_text, metadata) in enumerate(
                zip(input_data.chunks, input_data.metadata)
            ):
                lib_id = metadata.library_id

                # Check write access
                if not await server.access_service.check_library_access(
                    library_id=uuid.UUID(lib_id),
                    agent_id=agent_id,
                    for_write=True,
                ):
                    errors.append(UpsertError(
                        index=i,
                        error=f"Write access denied for library {lib_id}",
                    ))
                    continue

                if lib_id not in chunks_by_library:
                    chunks_by_library[lib_id] = []

                chunks_by_library[lib_id].append((i, chunk_text, metadata))

            # Process each library
            upserted_ids = []

            for lib_id, chunks in chunks_by_library.items():
                lib_uuid = uuid.UUID(lib_id)

                document_ids = []
                contents = []
                embeddings = []
                metadatas = []

                for i, chunk_text, metadata in chunks:
                    # Generate deterministic chunk ID
                    chunk_doc_id = ChromaDBService.generate_chunk_id(
                        library_id=lib_id,
                        doc_id=metadata.doc_id,
                        chunk_id=metadata.chunk_id,
                        path=metadata.path,
                    )
                    document_ids.append(chunk_doc_id)
                    contents.append(chunk_text)

                    # Generate embedding
                    try:
                        embedding = await embedding_service.generate_embedding(
                            chunk_text[:8000]  # Truncate for embedding
                        )
                        embeddings.append(embedding)
                    except Exception as e:
                        logger.error(
                            "upsert_embedding_error",
                            index=i,
                            error=str(e),
                        )
                        errors.append(UpsertError(
                            index=i,
                            error=f"Failed to generate embedding: {str(e)}",
                        ))
                        # Remove this chunk from the batch
                        document_ids.pop()
                        contents.pop()
                        continue

                    # Build metadata dict
                    meta_dict = {
                        "path": metadata.path,
                        "chunk_id": metadata.chunk_id,
                        "library_id": lib_id,
                    }

                    if metadata.doc_id:
                        meta_dict["doc_id"] = metadata.doc_id
                        meta_dict["file_id"] = metadata.doc_id  # Compatibility
                    if metadata.line_start is not None:
                        meta_dict["line_start"] = metadata.line_start
                    if metadata.line_end is not None:
                        meta_dict["line_end"] = metadata.line_end
                    if metadata.page is not None:
                        meta_dict["page"] = metadata.page
                    if metadata.offset_start is not None:
                        meta_dict["offset_start"] = metadata.offset_start
                    if metadata.offset_end is not None:
                        meta_dict["offset_end"] = metadata.offset_end
                    if metadata.hash:
                        meta_dict["hash"] = metadata.hash
                    if metadata.updated_at:
                        meta_dict["updated_at"] = metadata.updated_at
                    else:
                        meta_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
                    if metadata.language:
                        meta_dict["language"] = metadata.language
                    if metadata.chunk_type:
                        meta_dict["chunk_type"] = metadata.chunk_type
                    if metadata.name:
                        meta_dict["name"] = metadata.name
                    if metadata.file_name:
                        meta_dict["file_name"] = metadata.file_name
                    if metadata.mime_type:
                        meta_dict["mime_type"] = metadata.mime_type

                    metadatas.append(meta_dict)

                # Upsert to ChromaDB
                if document_ids:
                    success = await chroma_service.upsert_documents(
                        library_id=lib_uuid,
                        document_ids=document_ids,
                        contents=contents,
                        embeddings=embeddings,
                        metadatas=metadatas,
                    )

                    if success:
                        upserted_ids.extend(document_ids)
                    else:
                        for doc_id in document_ids:
                            errors.append(UpsertError(
                                index=0,  # Can't track individual failures
                                error=f"Failed to upsert batch to library {lib_id}",
                            ))

            # Log metrics
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "vector_upsert_complete",
                agent_id=agent_id,
                upserted_count=len(upserted_ids),
                error_count=len(errors),
                duration_ms=round(duration_ms, 2),
            )

            server.metrics["upsert_count"] += 1

            return UpsertOutput(
                upserted_count=len(upserted_ids),
                ids=upserted_ids,
                errors=errors,
            ).model_dump()

        except Exception as e:
            logger.error("vector_upsert_error", error=str(e))
            server.metrics["error_count"] += 1
            return UpsertOutput(
                upserted_count=0,
                ids=[],
                errors=[UpsertError(index=0, error=str(e))],
            ).model_dump()

    # =========================================================================
    # vector.get
    # =========================================================================

    async def vector_get(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch chunks by exact IDs."""
        try:
            input_data = GetInput(**arguments)
            agent_id = server.current_agent_id or "anonymous"

            # Parse IDs to extract library IDs
            # ID format: {library_id}:{doc_id}:chunk:{chunk_id}
            ids_by_library: Dict[str, List[str]] = {}

            for chunk_id in input_data.ids:
                parts = chunk_id.split(":")
                if len(parts) >= 1:
                    lib_id = parts[0]
                    if lib_id not in ids_by_library:
                        ids_by_library[lib_id] = []
                    ids_by_library[lib_id].append(chunk_id)

            items = []

            for lib_id, ids in ids_by_library.items():
                try:
                    lib_uuid = uuid.UUID(lib_id)
                except ValueError:
                    continue

                # Check read access
                if not await server.access_service.check_library_access(
                    library_id=lib_uuid,
                    agent_id=agent_id,
                    for_write=False,
                ):
                    continue

                lib_items = await chroma_service.get_documents(
                    library_id=lib_uuid,
                    ids=ids,
                )

                for item in lib_items:
                    items.append(GetItem(
                        id=item.get("id", ""),
                        text=item.get("text", ""),
                        metadata=item.get("metadata", {}),
                    ))

            return GetOutput(items=items).model_dump()

        except Exception as e:
            logger.error("vector_get_error", error=str(e))
            server.metrics["error_count"] += 1
            return GetOutput(items=[]).model_dump()

    # =========================================================================
    # vector.delete
    # =========================================================================

    async def vector_delete(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Delete chunks by filter.

        Supports deletion by:
        - doc_id: Delete all chunks for a document
        - path_prefix: Delete chunks with paths starting with prefix
        - library_id: Delete all chunks in a library
        """
        try:
            input_data = DeleteInput(**arguments)
            agent_id = server.current_agent_id or "anonymous"
            where = input_data.where

            # Validate that at least one filter is provided
            if not where.doc_id and not where.path_prefix and not where.library_id:
                return DeleteOutput(deleted_count=0).model_dump()

            deleted_count = 0

            # Delete by library_id (delete entire collection)
            if where.library_id:
                lib_uuid = uuid.UUID(where.library_id)

                # Check write access
                if not await server.access_service.check_library_access(
                    library_id=lib_uuid,
                    agent_id=agent_id,
                    for_write=True,
                ):
                    logger.warning(
                        "vector_delete_access_denied",
                        library_id=where.library_id,
                        agent_id=agent_id,
                    )
                    return DeleteOutput(deleted_count=0).model_dump()

                # Get count before deletion
                count = await chroma_service.get_collection_count(lib_uuid)

                success = await chroma_service.delete_collection(lib_uuid)
                if success:
                    deleted_count = count

            # Delete by doc_id
            elif where.doc_id:
                # Need to search all accessible libraries
                library_ids = await server.access_service.get_accessible_libraries(
                    agent_id=agent_id,
                    for_write=True,
                )

                for lib_uuid in library_ids:
                    count = await chroma_service.delete_by_doc_id(
                        library_id=lib_uuid,
                        doc_id=where.doc_id,
                    )
                    deleted_count += count

            # Delete by path_prefix
            elif where.path_prefix:
                library_ids = await server.access_service.get_accessible_libraries(
                    agent_id=agent_id,
                    for_write=True,
                )

                for lib_uuid in library_ids:
                    count = await chroma_service.delete_by_path_prefix(
                        library_id=lib_uuid,
                        path_prefix=where.path_prefix,
                    )
                    deleted_count += count

            logger.info(
                "vector_delete_complete",
                agent_id=agent_id,
                deleted_count=deleted_count,
                where=where.model_dump(),
            )

            server.metrics["delete_count"] += 1

            return DeleteOutput(deleted_count=deleted_count).model_dump()

        except Exception as e:
            logger.error("vector_delete_error", error=str(e))
            server.metrics["error_count"] += 1
            return DeleteOutput(deleted_count=0).model_dump()

    # Register all tools
    server.register_tool("vector.query", vector_query)
    server.register_tool("vector.upsert_documents", vector_upsert_documents)
    server.register_tool("vector.get", vector_get)
    server.register_tool("vector.delete", vector_delete)
