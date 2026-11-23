import logging
from typing import Any

from requests.exceptions import RequestException
from tavily.errors import (
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    TimeoutError as TavilyTimeoutError,
    UsageLimitExceededError,
)

from app.core.config import settings
from app.services.rag.errors import (
    RAGConfigurationError,
    RAGProviderError,
)

logger = logging.getLogger(__name__)


class WebSearchService:
    def __init__(self) -> None:
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        configured_key = settings.tavily_api_key
        api_key = (
            configured_key.get_secret_value().strip()
            if configured_key is not None
            else ""
        )
        if not api_key:
            raise RAGConfigurationError("TAVILY_API_KEY is not configured")

        try:
            from tavily import TavilyClient
        except ImportError as error:
            raise RAGConfigurationError(
                "Install the backend RAG dependencies before using search"
            ) from error

        self._client = TavilyClient(api_key=api_key)
        return self._client

    def search(self, query: str) -> list[dict[str, Any]]:
        client = self._get_client()
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=settings.rag_max_search_results,
                include_raw_content=True,
            )
        except (InvalidAPIKeyError, MissingAPIKeyError) as error:
            raise RAGConfigurationError("TAVILY_API_KEY is invalid") from error
        except (
            BadRequestError,
            ForbiddenError,
            UsageLimitExceededError,
            TavilyTimeoutError,
            RequestException,
        ) as error:
            logger.exception("Tavily maintenance search failed")
            raise RAGProviderError(
                "The web search provider could not complete the request"
            ) from error

        if not isinstance(response, dict):
            raise RAGProviderError("The web search provider returned invalid results")
        results = response.get("results", [])
        if not isinstance(results, list):
            raise RAGProviderError("The web search provider returned invalid results")
        return [result for result in results if isinstance(result, dict)]

    def search_many(self, queries: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for query in queries:
            for result in self.search(query):
                url = result.get("url")
                if isinstance(url, str):
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                results.append(result)
        return results

    def extract(self, urls: list[str]) -> dict[str, dict[str, Any]]:
        if not urls:
            return {}

        client = self._get_client()
        try:
            response = client.extract(urls=urls)
        except (InvalidAPIKeyError, MissingAPIKeyError) as error:
            raise RAGConfigurationError("TAVILY_API_KEY is invalid") from error
        except (
            BadRequestError,
            ForbiddenError,
            UsageLimitExceededError,
            TavilyTimeoutError,
            RequestException,
        ) as error:
            logger.exception("Tavily content extraction failed")
            raise RAGProviderError(
                "The web content provider could not extract search results"
            ) from error

        if not isinstance(response, dict):
            raise RAGProviderError(
                "The web content provider returned invalid extraction results"
            )
        results = response.get("results", [])
        if not isinstance(results, list):
            raise RAGProviderError(
                "The web content provider returned invalid extraction results"
            )
        return {
            result["url"]: result
            for result in results
            if isinstance(result, dict)
            and isinstance(result.get("url"), str)
        }
