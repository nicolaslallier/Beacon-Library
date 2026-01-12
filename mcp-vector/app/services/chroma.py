"""ChromaDB service for vector storage and search."""

import uuid
from typing import Any, Dict, List, Optional

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class ChromaDBService:
    """Service for vector storage and search using ChromaDB."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        import chromadb

        self.host = host or settings.chromadb_host
        self.port = port or settings.chromadb_port
        self._client = chromadb.HttpClient(host=self.host, port=self.port)
        self._collection_cache: Dict[str, Any] = {}

    @staticmethod
    def _collection_name(library_id: uuid.UUID) -> str:
        """Generate collection name for a library."""
        return f"beacon_lib_{str(library_id).replace('-', '_')}"

    @staticmethod
    def generate_chunk_id(
        library_id: str,
        doc_id: Optional[str],
        chunk_id: int,
        path: str,
    ) -> str:
        """Generate a deterministic chunk ID for idempotent upserts.

        Format: {library_id}:{doc_id}:chunk:{chunk_id}
        Or if no doc_id: {library_id}:{path_hash}:chunk:{chunk_id}
        """
        if doc_id:
            return f"{library_id}:{doc_id}:chunk:{chunk_id}"
        else:
            # Use path hash as fallback for doc_id
            import hashlib
            path_hash = hashlib.sha256(path.encode()).hexdigest()[:16]
            return f"{library_id}:{path_hash}:chunk:{chunk_id}"

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
                    distance = data["distances"][0][i] if data.get("distances") else 0
                    # Convert distance to score (0=best distance -> 1=best score)
                    # ChromaDB uses L2 distance by default
                    score = max(0, 1 - distance) if distance < 1 else 1 / (1 + distance)

                    results.append({
                        "id": doc_id,
                        "text": (
                            data["documents"][0][i]
                            if data.get("documents") else ""
                        ),
                        "metadata": (
                            data["metadatas"][0][i]
                            if data.get("metadatas") else {}
                        ),
                        "score": score,
                        "distance": distance,
                    })

            return results
        except Exception as e:
            logger.error(
                "chromadb_search_error",
                library_id=str(library_id),
                error=str(e),
            )
            return []

    async def upsert_documents(
        self,
        library_id: uuid.UUID,
        document_ids: List[str],
        contents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> bool:
        """Upsert multiple documents to the vector store."""
        try:
            collection = self._get_or_create_collection(library_id)
            collection.upsert(
                ids=document_ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas,
            )
            return True
        except Exception as e:
            logger.error(
                "chromadb_upsert_error",
                count=len(document_ids),
                error=str(e),
            )
            return False

    async def get_documents(
        self,
        library_id: uuid.UUID,
        ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Get documents by their IDs."""
        try:
            collection = self._get_or_create_collection(library_id)
            results = collection.get(
                ids=ids,
                include=["documents", "metadatas"],
            )

            items = []
            if results.get("ids"):
                for i, doc_id in enumerate(results["ids"]):
                    items.append({
                        "id": doc_id,
                        "text": results["documents"][i] if results.get("documents") else "",
                        "metadata": results["metadatas"][i] if results.get("metadatas") else {},
                    })

            return items
        except Exception as e:
            logger.error(
                "chromadb_get_error",
                ids=ids,
                error=str(e),
            )
            return []

    async def delete_by_filter(
        self,
        library_id: uuid.UUID,
        where: Dict[str, Any],
    ) -> int:
        """Delete documents matching a filter."""
        try:
            collection = self._get_or_create_collection(library_id)

            # First, get the count of matching documents
            existing = collection.get(
                where=where,
                include=[],  # Just need IDs
            )
            count = len(existing.get("ids", []))

            if count > 0:
                collection.delete(where=where)

            return count
        except Exception as e:
            logger.error(
                "chromadb_delete_error",
                library_id=str(library_id),
                where=where,
                error=str(e),
            )
            return 0

    async def delete_by_doc_id(
        self,
        library_id: uuid.UUID,
        doc_id: str,
    ) -> int:
        """Delete all chunks for a document."""
        return await self.delete_by_filter(
            library_id=library_id,
            where={"doc_id": doc_id},
        )

    async def delete_by_path_prefix(
        self,
        library_id: uuid.UUID,
        path_prefix: str,
    ) -> int:
        """Delete all chunks with paths matching prefix.

        Note: ChromaDB doesn't support prefix queries natively,
        so we need to get all and filter.
        """
        try:
            collection = self._get_or_create_collection(library_id)

            # Get all documents with their metadata
            all_docs = collection.get(
                include=["metadatas"],
            )

            if not all_docs.get("ids"):
                return 0

            # Find IDs matching the path prefix
            ids_to_delete = []
            for i, doc_id in enumerate(all_docs["ids"]):
                metadata = all_docs["metadatas"][i] if all_docs.get("metadatas") else {}
                path = metadata.get("path", "")
                if path.startswith(path_prefix):
                    ids_to_delete.append(doc_id)

            if ids_to_delete:
                collection.delete(ids=ids_to_delete)

            return len(ids_to_delete)
        except Exception as e:
            logger.error(
                "chromadb_delete_by_prefix_error",
                library_id=str(library_id),
                path_prefix=path_prefix,
                error=str(e),
            )
            return 0

    async def delete_collection(self, library_id: uuid.UUID) -> bool:
        """Delete the entire collection for a library."""
        collection_name = self._collection_name(library_id)
        try:
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

    async def get_collection_count(self, library_id: uuid.UUID) -> int:
        """Get the number of documents in a collection."""
        try:
            collection = self._get_or_create_collection(library_id)
            return collection.count()
        except Exception as e:
            logger.error(
                "chromadb_count_error",
                library_id=str(library_id),
                error=str(e),
            )
            return 0

    def list_collections(self) -> List[str]:
        """List all collection names."""
        try:
            collections = self._client.list_collections()
            return [c.name for c in collections]
        except Exception as e:
            logger.error("chromadb_list_collections_error", error=str(e))
            return []
