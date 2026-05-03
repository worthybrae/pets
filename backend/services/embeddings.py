"""Embedding service using OpenAI text-embedding-3-small."""

import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings using OpenAI text-embedding-3-small (1536 dimensions)."""

    def __init__(self):
        self._client: AsyncOpenAI | None = None
        self.model = "text-embedding-3-small"  # 1536 dimensions

    @property
    def client(self) -> AsyncOpenAI:
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        if not text.strip():
            # Return zero vector for empty text
            return [0.0] * 1536

        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        # Filter out empty strings, but keep track of indices
        non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not non_empty:
            return [[0.0] * 1536 for _ in texts]

        # Call API with non-empty texts
        response = await self.client.embeddings.create(
            model=self.model,
            input=[t for _, t in non_empty],
        )

        # Map results back to original indices
        results: list[list[float]] = [[0.0] * 1536 for _ in texts]
        for idx, embedding_obj in enumerate(response.data):
            original_idx = non_empty[idx][0]
            results[original_idx] = embedding_obj.embedding

        return results


# Singleton instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get the singleton EmbeddingService instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
