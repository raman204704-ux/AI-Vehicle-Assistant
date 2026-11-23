from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.services.rag.embeddings import EmbeddingService
from app.services.rag.vector_store import VectorStore


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def retrieve(
        self,
        query: str,
        vehicle: dict[str, Any],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        query_embedding = self.embedding_service.generate_query_embedding(query)
        context_key = self.vector_store._context_key(vehicle)
        results = self.vector_store.search(
            query_embedding=query_embedding,
            vehicle_id=vehicle["id"],
            context_key=context_key,
            limit=limit,
        )

        documents = results.get("documents") or [[]]
        metadatas = results.get("metadatas") or [[]]
        distances = results.get("distances") or [[]]
        if not documents or not documents[0]:
            return []

        retrieved: list[dict[str, Any]] = []
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.rag_cache_ttl_days
        )
        for index, content in enumerate(documents[0]):
            metadata = metadatas[0][index] if index < len(metadatas[0]) else {}
            distance = distances[0][index] if index < len(distances[0]) else None
            retrieved_at = metadata.get("retrieved_at")
            try:
                cached_at = datetime.fromisoformat(
                    retrieved_at.replace("Z", "+00:00")
                )
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
            except (AttributeError, TypeError, ValueError):
                continue
            if cached_at < cutoff:
                continue
            if (
                isinstance(distance, (int, float))
                and distance > settings.rag_max_cosine_distance
            ):
                continue
            retrieved.append(
                {
                    "content": content,
                    "metadata": metadata,
                    "distance": distance,
                }
            )
        return retrieved
