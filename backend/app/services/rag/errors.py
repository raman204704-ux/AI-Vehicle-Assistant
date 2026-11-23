class RAGError(Exception):
    """Base error for the retrieval-augmented maintenance assistant."""


class RAGConfigurationError(RAGError):
    """Raised when an external provider or local model is not configured."""


class RAGProviderError(RAGError):
    """Raised when a search, model, or vector-store provider fails."""
