import math
import logging
from typing import Any

from app.core.config import settings
from app.services.rag.errors import (
    RAGConfigurationError,
    RAGProviderError,
)

logger = logging.getLogger(__name__)


class Reranker:
    RELEVANCE_WEIGHT = 0.8
    RELIABILITY_WEIGHT = 0.2

    def __init__(self) -> None:
        self._model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as error:
            raise RAGConfigurationError(
                "Install the backend RAG dependencies before reranking results"
            ) from error

        try:
            self._model = CrossEncoder(settings.reranker_model)
        except Exception as error:
            logger.exception("Could not load the configured reranker model")
            raise RAGProviderError("The reranker model could not be loaded") from error
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not documents or top_k <= 0:
            return []
        pairs = [[query, document["content"]] for document in documents]
        try:
            scores = self._get_model().predict(
                pairs,
                show_progress_bar=False,
            )
        except RAGConfigurationError:
            raise
        except Exception as error:
            logger.exception("Maintenance result reranking failed")
            raise RAGProviderError("Could not rerank maintenance information") from error

        if len(scores) != len(documents):
            raise RAGProviderError(
                "The reranker returned an unexpected number of scores"
            )
        ranked = []
        for document, score in zip(documents, scores):
            try:
                relevance_score = float(score)
            except (TypeError, ValueError, OverflowError) as error:
                raise RAGProviderError(
                    "The reranker returned an invalid score"
                ) from error
            if not math.isfinite(relevance_score):
                raise RAGProviderError(
                    "The reranker returned a non-finite score"
                )
            priority = document["metadata"].get("source_priority", 1)
            if not isinstance(priority, (int, float)) or not math.isfinite(priority):
                priority = 1
            reliability_score = (min(max(float(priority), 1), 5) - 1) / 4
            normalized_relevance = self._sigmoid(relevance_score)
            ranked_document = dict(document)
            ranked_document["rerank_score"] = relevance_score
            ranked_document["relevance_score"] = normalized_relevance
            ranked_document["reliability_score"] = reliability_score
            ranked_document["combined_score"] = (
                self.RELEVANCE_WEIGHT * normalized_relevance
                + self.RELIABILITY_WEIGHT * reliability_score
            )
            ranked.append(ranked_document)
        ranked.sort(
            key=lambda document: document["combined_score"],
            reverse=True,
        )
        return ranked[:top_k]

    @staticmethod
    def _sigmoid(score: float) -> float:
        if score >= 0:
            exponent = math.exp(-score)
            return 1 / (1 + exponent)
        exponent = math.exp(score)
        return exponent / (1 + exponent)
