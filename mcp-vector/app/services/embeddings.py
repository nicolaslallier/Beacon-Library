"""Ollama embedding service for generating vector embeddings."""

from typing import List, Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class OllamaEmbeddingService:
    """Service for generating embeddings using Ollama."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = base_url or settings.ollama_url
        self.model = model or settings.ollama_embedding_model
        self.timeout = timeout or settings.embedding_timeout

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            Exception: If embedding generation fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding", [])

                if not embedding:
                    raise ValueError("Empty embedding returned from Ollama")

                return embedding

            except httpx.HTTPStatusError as e:
                logger.error(
                    "ollama_embedding_http_error",
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise
            except httpx.TimeoutException as e:
                logger.error(
                    "ollama_embedding_timeout",
                    timeout=self.timeout,
                    error=str(e),
                )
                raise
            except Exception as e:
                logger.error("ollama_embedding_error", error=str(e))
                raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Note: Ollama doesn't support batch embeddings natively,
        so we process them sequentially.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = await self.generate_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(
                    "batch_embedding_error",
                    index=i,
                    error=str(e),
                )
                # Return empty embedding for failed items
                # The caller should handle this
                embeddings.append([])

        return embeddings

    async def health_check(self) -> bool:
        """Check if Ollama is available and the model is loaded."""
        async with httpx.AsyncClient() as client:
            try:
                # Check if server is up
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0,
                )
                response.raise_for_status()
                data = response.json()

                # Check if our model is available
                models = data.get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]

                if self.model.split(":")[0] not in model_names:
                    logger.warning(
                        "ollama_model_not_found",
                        model=self.model,
                        available=model_names,
                    )
                    # Model not pulled yet, but server is up
                    return True

                return True

            except Exception as e:
                logger.error("ollama_health_check_error", error=str(e))
                return False

    async def ensure_model_available(self) -> bool:
        """Ensure the embedding model is available (pull if needed)."""
        async with httpx.AsyncClient() as client:
            try:
                # Check if model exists
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0,
                )
                response.raise_for_status()
                data = response.json()

                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]

                # Check both full name and base name
                if self.model in model_names:
                    return True

                base_model = self.model.split(":")[0]
                if any(m.startswith(base_model) for m in model_names):
                    return True

                # Model not found, try to pull it
                logger.info("ollama_pulling_model", model=self.model)

                pull_response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model},
                    timeout=300.0,  # Pulling can take a while
                )
                pull_response.raise_for_status()

                return True

            except Exception as e:
                logger.error(
                    "ollama_ensure_model_error",
                    model=self.model,
                    error=str(e),
                )
                return False
