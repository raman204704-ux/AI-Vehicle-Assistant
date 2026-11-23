import logging
from typing import Any

from app.core.config import settings
from app.services.rag.errors import (
    RAGConfigurationError,
    RAGProviderError,
)

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self._model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RAGConfigurationError(
                "Install the backend RAG dependencies before generating embeddings"
            ) from error

        try:
            self._model = SentenceTransformer(settings.embedding_model)
        except Exception as error:
            logger.exception("Could not load the configured embedding model")
            raise RAGProviderError(
                "The embedding model could not be loaded"
            ) from error
        return self._model

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self._get_model().encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except RAGConfigurationError:
            raise
        except Exception as error:
            logger.exception("Embedding generation failed")
            raise RAGProviderError("Could not generate document embeddings") from error
        return vectors.tolist()

    def generate_query_embedding(self, query: str) -> list[float]:
        try:
            vector = self._get_model().encode(
                query,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except RAGConfigurationError:
            raise
        except Exception as error:
            logger.exception("Query embedding generation failed")
            raise RAGProviderError("Could not generate a query embedding") from error
        return vector.tolist()
