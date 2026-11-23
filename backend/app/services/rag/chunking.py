from app.core.config import settings


class TextChunker:
    def __init__(
        self,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.rag_chunk_size_words
        self.overlap = (
            settings.rag_chunk_overlap_words if overlap is None else overlap
        )
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.overlap < 0 or self.overlap >= self.chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")

    def split_text(self, text: str) -> list[str]:
        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        step = self.chunk_size - self.overlap
        for start in range(0, len(words), step):
            chunk = " ".join(words[start : start + self.chunk_size])
            if chunk:
                chunks.append(chunk)
            if start + self.chunk_size >= len(words):
                break
        return chunks
