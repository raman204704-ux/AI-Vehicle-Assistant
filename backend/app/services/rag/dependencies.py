from threading import Lock

from app.services.rag.rag_service import RAGService

_rag_service: RAGService | None = None
_rag_service_lock = Lock()


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        with _rag_service_lock:
            if _rag_service is None:
                _rag_service = RAGService()
    return _rag_service
