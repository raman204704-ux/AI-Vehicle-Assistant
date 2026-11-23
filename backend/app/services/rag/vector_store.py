import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.rag.errors import (
    RAGConfigurationError,
    RAGProviderError,
)

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self) -> None:
        self._client: Any | None = None
        self._collection: Any | None = None

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection

        try:
            import chromadb
        except ImportError as error:
            raise RAGConfigurationError(
                "Install the backend RAG dependencies before using the vector store"
            ) from error

        persist_directory = Path(settings.chroma_persist_directory)
        persist_directory.mkdir(parents=True, exist_ok=True)
        try:
            self._client = chromadb.PersistentClient(path=str(persist_directory))
            self._collection = self._client.get_or_create_collection(
                name="vehicle_maintenance",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as error:
            logger.exception("Could not open the ChromaDB collection")
            raise RAGProviderError("The maintenance vector store is unavailable") from error
        return self._collection

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._collection = None

    @staticmethod
    def _context_key(vehicle: dict[str, Any]) -> str:
        profile = {
            "vehicle_id": vehicle["id"],
            "manufacturer": vehicle["manufacturer"].strip().casefold(),
            "model": vehicle["model"].strip().casefold(),
            "year": vehicle["year"],
            "fuel_type": vehicle["fuel_type"].strip().casefold(),
            "engine": (vehicle.get("engine") or "").strip().casefold(),
            "market": (vehicle.get("market") or "").strip().casefold(),
        }
        serialized = json.dumps(profile, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def store_documents(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        source: dict[str, Any],
        vehicle: dict[str, Any],
    ) -> int:
        if not chunks or len(chunks) != len(embeddings):
            raise ValueError("Each document chunk must have one embedding")

        content_hash = hashlib.sha256(
            source["content"].encode("utf-8")
        ).hexdigest()
        context_key = self._context_key(vehicle)
        collection = self._get_collection()

        try:
            existing = collection.get(
                where={
                    "$and": [
                        {"context_key": context_key},
                        {"content_hash": content_hash},
                    ]
                },
                include=["metadatas"],
            )
            if existing["ids"]:
                return 0

            retrieved_at = datetime.now(timezone.utc).isoformat()
            ids: list[str] = []
            metadatas: list[dict[str, Any]] = []
            for index in range(len(chunks)):
                ids.append(
                    hashlib.sha256(
                        f"{context_key}:{content_hash}:{index}".encode("utf-8")
                    ).hexdigest()
                )
                metadatas.append(
                    {
                        "source_url": source["url"],
                        "source_title": source["title"],
                        "source_type": source["source_type"],
                        "source_priority": source["source_priority"],
                        "vehicle_id": vehicle["id"],
                        "manufacturer": vehicle["manufacturer"],
                        "model": vehicle["model"],
                        "year": vehicle["year"],
                        "fuel_type": vehicle["fuel_type"],
                        "engine": vehicle.get("engine") or "",
                        "market": vehicle.get("market") or "",
                        "context_key": context_key,
                        "content_hash": content_hash,
                        "retrieved_at": retrieved_at,
                        "chunk_index": index,
                    }
                )

            collection.upsert(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as error:
            logger.exception("Could not index maintenance search results")
            raise RAGProviderError(
                "Maintenance information could not be indexed"
            ) from error
        return len(chunks)

    def refresh_cached_source(
        self,
        source: dict[str, Any],
        vehicle: dict[str, Any],
    ) -> bool:
        content_hash = hashlib.sha256(
            source["content"].encode("utf-8")
        ).hexdigest()
        collection = self._get_collection()
        try:
            existing = collection.get(
                where={
                    "$and": [
                        {"context_key": self._context_key(vehicle)},
                        {"content_hash": content_hash},
                    ]
                },
                include=["metadatas"],
            )
            if not existing["ids"]:
                return False

            refreshed_at = datetime.now(timezone.utc).isoformat()
            metadatas = []
            for metadata in existing["metadatas"]:
                updated = dict(metadata)
                updated["retrieved_at"] = refreshed_at
                metadatas.append(updated)
            collection.update(
                ids=existing["ids"],
                metadatas=metadatas,
            )
        except Exception as error:
            logger.exception("Could not refresh cached maintenance source")
            raise RAGProviderError(
                "The maintenance source cache could not be refreshed"
            ) from error
        return True

    def search(
        self,
        query_embedding: list[float],
        vehicle_id: int,
        context_key: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        collection = self._get_collection()
        try:
            count = collection.count()
            if count == 0:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            return collection.query(
                query_embeddings=[query_embedding],
                n_results=min(limit, count),
                where={
                    "$and": [
                        {"vehicle_id": vehicle_id},
                        {"context_key": context_key},
                    ]
                },
                include=["documents", "metadatas", "distances"],
            )
        except Exception as error:
            logger.exception("Maintenance knowledge retrieval failed")
            raise RAGProviderError(
                "Maintenance information could not be retrieved"
            ) from error
