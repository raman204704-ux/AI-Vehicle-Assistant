import math
from typing import Any
from urllib.parse import urlsplit

import trafilatura

from app.core.config import settings


class ContentExtractor:
    def extract(self, search_result: dict[str, Any]) -> dict[str, Any] | None:
        url = search_result.get("url")
        if not isinstance(url, str):
            return None

        raw_content = search_result.get("raw_content")
        content = raw_content if isinstance(raw_content, str) else ""
        if not content:
            result_content = search_result.get("content")
            content = result_content if isinstance(result_content, str) else ""

        if "<html" in content[:1000].lower() or "<body" in content[:1000].lower():
            content = trafilatura.extract(
                content,
                url=url,
                include_comments=False,
                include_tables=True,
            ) or ""

        content = " ".join(content.split())
        content = content[: settings.rag_max_source_characters]
        if len(content) < settings.rag_min_source_characters:
            return None

        title = search_result.get("title")
        score = search_result.get("score", 0.0)
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            score = 0.0
        return {
            "title": (
                title.strip()
                if isinstance(title, str) and title.strip()
                else "Untitled source"
            ),
            "url": url,
            "content": content,
            "score": float(score),
            "host": urlsplit(url).hostname or "",
        }
