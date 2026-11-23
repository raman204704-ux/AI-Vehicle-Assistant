import ipaddress
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from app.core.config import settings
from app.services.rag.answer_generator import AnswerGenerator
from app.services.rag.chunking import TextChunker
from app.services.rag.content_extractor import ContentExtractor
from app.services.rag.embeddings import EmbeddingService
from app.services.rag.reranker import Reranker
from app.services.rag.retrieval import RetrievalService
from app.services.rag.vector_store import VectorStore
from app.services.rag.web_search import WebSearchService

logger = logging.getLogger(__name__)

_MANUFACTURER_DOMAINS = {
    "tata": ("tatamotors.com",),
    "tatamotors": ("tatamotors.com",),
    "royalenfield": ("royalenfield.com",),
    "mahindra": ("mahindra.com",),
    "maruti": ("marutisuzuki.com",),
    "marutisuzuki": ("marutisuzuki.com",),
    "hyundai": ("hyundai.com",),
    "toyota": ("toyotabharat.com", "toyota.com"),
    "honda": ("hondacarindia.com", "honda.com"),
    "kia": ("kia.com",),
}
_REPUTABLE_AUTOMOTIVE_DOMAINS = {
    "ackodrive.com",
    "autocarindia.com",
    "carandbike.com",
    "cardekho.com",
    "carwale.com",
    "spinny.com",
    "zigwheels.com",
}
_AUTOMOTIVE_HOST_TERMS = {
    "auto",
    "automotive",
    "bike",
    "car",
    "cars",
    "motor",
    "motors",
    "vehicle",
    "vehicles",
}
_GOVERNMENT_DOMAINS = {
    "gov",
    "gov.au",
    "gov.in",
    "gov.uk",
    "nic.in",
}
_DOCUMENTATION_TERMS = {
    "manual",
    "maintenance",
    "schedule",
    "service",
    "interval",
    "owner",
}
CITATION_VALIDATION_FALLBACK = (
    "I couldn't verify the generated citations against the retrieved sources, "
    "so I can't provide a grounded maintenance answer. Please consult the "
    "manufacturer's official documentation or an authorized service centre."
)


class RAGService:
    def __init__(self) -> None:
        self.web_search = WebSearchService()
        self.extractor = ContentExtractor()
        self.chunker = TextChunker()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()
        self.retrieval = RetrievalService(
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
        )
        self.reranker = Reranker()
        self.answer_generator = AnswerGenerator()

    @staticmethod
    def _is_public_source_url(url: str) -> bool:
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            if (
                parsed.scheme not in {"http", "https"}
                or not host
                or parsed.username is not None
                or parsed.password is not None
                or host.casefold() == "localhost"
                or host.casefold().endswith(
                    (
                        ".localhost",
                        ".local",
                        ".internal",
                        ".test",
                        ".example",
                        ".invalid",
                        ".onion",
                    )
                )
            ):
                return False
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                return "." in host
            return address.is_global
        except ValueError:
            return False

    @staticmethod
    def _source_quality(
        host: str,
        manufacturer: str,
        title: str = "",
        url: str = "",
    ) -> tuple[int, str]:
        normalized_host = host.casefold().rstrip(".")
        documentation_text = f"{title} {url}".casefold()
        domains = RAGService._official_manufacturer_domains(manufacturer)
        if RAGService._host_matches_domain(normalized_host, domains):
            if any(term in documentation_text for term in _DOCUMENTATION_TERMS):
                return 5, "manufacturer_documentation"
            return 4, "manufacturer"
        if RAGService._host_matches_domain(
            normalized_host,
            _GOVERNMENT_DOMAINS,
        ):
            return 4, "government"
        if RAGService._host_matches_domain(
            normalized_host,
            _REPUTABLE_AUTOMOTIVE_DOMAINS,
        ):
            return 3, "reputable_automotive_publication"
        if any(term in normalized_host.split(".") for term in _AUTOMOTIVE_HOST_TERMS):
            return 2, "general_automotive_website"
        return 1, "unverified_web"

    @staticmethod
    def _host_matches_domain(host: str, domains: tuple[str, ...] | set[str]) -> bool:
        return any(host == domain or host.endswith(f".{domain}") for domain in domains)

    @staticmethod
    def _official_manufacturer_domains(manufacturer: str) -> tuple[str, ...]:
        manufacturer_slug = "".join(
            re.findall(r"[a-z0-9]+", manufacturer.casefold())
        )
        return next(
            (
                domains
                for alias, domains in _MANUFACTURER_DOMAINS.items()
                if manufacturer_slug == alias or manufacturer_slug.startswith(alias)
            ),
            (),
        )

    @staticmethod
    def _build_search_queries(
        question: str,
        vehicle: dict[str, Any],
    ) -> list[str]:
        broad_query = RAGService._build_search_query(question, vehicle)
        manufacturer = vehicle["manufacturer"]
        domains = RAGService._official_manufacturer_domains(manufacturer)
        official_terms = (
            "owner manual maintenance schedule service intervals"
        )
        targeted_queries = [
            f"site:{domain} {broad_query} {official_terms}"
            for domain in domains
        ]
        if not targeted_queries:
            targeted_queries.append(
                f"{broad_query} official {manufacturer} {official_terms}"
            )
        return list(dict.fromkeys([*targeted_queries, broad_query]))

    @staticmethod
    def _build_search_query(
        question: str,
        vehicle: dict[str, Any],
    ) -> str:
        details = [
            vehicle["manufacturer"],
            vehicle["model"],
            str(vehicle["year"]),
            vehicle["fuel_type"],
        ]
        if vehicle.get("engine"):
            details.append(vehicle["engine"])
        if vehicle.get("market"):
            details.append(vehicle["market"])
        details.extend([question, "maintenance schedule manufacturer documentation"])
        return " ".join(details)

    def _extract_documents(
        self,
        search_results: list[dict[str, Any]],
        manufacturer: str,
    ) -> list[dict[str, Any]]:
        unique_results: dict[str, dict[str, Any]] = {}
        for result in search_results:
            url = result.get("url")
            if not isinstance(url, str) or not self._is_public_source_url(url):
                continue
            unique_results.setdefault(url, result)

        extracted_documents: list[dict[str, Any]] = []
        needs_extraction: dict[str, dict[str, Any]] = {}
        for url, result in unique_results.items():
            extracted = self.extractor.extract(result)
            if extracted is None:
                needs_extraction[url] = result
                continue
            priority, source_type = self._source_quality(
                extracted["host"],
                manufacturer,
                extracted["title"],
                extracted["url"],
            )
            extracted["source_priority"] = priority
            extracted["source_type"] = source_type
            extracted_documents.append(extracted)

        if needs_extraction:
            expanded = self.web_search.extract(list(needs_extraction))
            for url, result in needs_extraction.items():
                extracted_result = expanded.get(url)
                if extracted_result is None:
                    continue
                merged = dict(result)
                merged.update(extracted_result)
                extracted = self.extractor.extract(merged)
                if extracted is None:
                    continue
                priority, source_type = self._source_quality(
                    extracted["host"],
                    manufacturer,
                    extracted["title"],
                    extracted["url"],
                )
                extracted["source_priority"] = priority
                extracted["source_type"] = source_type
                extracted_documents.append(extracted)

        extracted_documents.sort(
            key=lambda document: (
                document["source_priority"],
                document["score"],
            ),
            reverse=True,
        )
        return extracted_documents

    def _index_documents(
        self,
        documents: list[dict[str, Any]],
        vehicle: dict[str, Any],
    ) -> int:
        indexed_count = 0
        for document in documents:
            if self.vector_store.refresh_cached_source(document, vehicle):
                continue
            chunks = self.chunker.split_text(document["content"])
            if not chunks:
                continue
            embeddings = self.embedding_service.generate_embeddings(chunks)
            indexed_count += self.vector_store.store_documents(
                chunks=chunks,
                embeddings=embeddings,
                source=document,
                vehicle=vehicle,
            )
        return indexed_count

    def _build_answer_context(
        self,
        documents: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, str]]]:
        context_parts: list[str] = []
        sources: list[dict[str, str]] = []
        source_ids: dict[str, str] = {}
        source_chunk_counts: dict[str, int] = {}
        context_length = 0

        for document in documents:
            metadata = document["metadata"]
            url = metadata.get("source_url", "")
            if not url or source_chunk_counts.get(url, 0) >= 2:
                continue

            source_id = source_ids.get(url)
            is_new_source = source_id is None
            if source_id is None:
                source_id = f"S{len(source_ids) + 1}"

            excerpt = json.dumps(
                {
                    "source_id": source_id,
                    "source_type": metadata.get("source_type", "web"),
                    "title": metadata.get("source_title", "Untitled source"),
                    "url": url,
                    "untrusted_content": document["content"],
                },
                ensure_ascii=False,
            )
            if (
                context_length + len(excerpt)
                > settings.rag_max_context_characters
            ):
                if not context_parts:
                    excerpt = excerpt[: settings.rag_max_context_characters]
                else:
                    break
            if is_new_source:
                source_ids[url] = source_id
                sources.append(
                    {
                        "source_id": source_id,
                        "title": metadata.get("source_title", "Untitled source"),
                        "url": url,
                        "source_type": metadata.get("source_type", "web"),
                        "retrieved_at": metadata.get("retrieved_at", ""),
                    }
                )
            context_parts.append(excerpt)
            context_length += len(excerpt)
            source_chunk_counts[url] = source_chunk_counts.get(url, 0) + 1

        return "\n\n".join(context_parts), sources

    @staticmethod
    def _validate_answer_citations(
        answer: str,
        sources: list[dict[str, str]],
    ) -> str:
        if not sources:
            return answer

        valid_ids = {source["source_id"] for source in sources}
        cited_ids = set(re.findall(r"\[(S[^\]]+)\]", answer))
        invalid_ids = cited_ids - valid_ids
        if not cited_ids or invalid_ids:
            logger.warning(
                "RAG answer citations failed validation",
                extra={
                    "invalid_citation_ids": sorted(invalid_ids),
                    "citation_missing": not cited_ids,
                },
            )
            return CITATION_VALIDATION_FALLBACK
        return answer

    def ask(
        self,
        question: str,
        vehicle: dict[str, Any],
        assistant_instructions: str | None = None,
        search_query: str | None = None,
    ) -> dict[str, Any]:
        retrieval_question = search_query or question
        search_queries = self._build_search_queries(retrieval_question, vehicle)
        search_results = self.web_search.search_many(search_queries)
        documents = self._extract_documents(
            search_results,
            vehicle["manufacturer"],
        )
        indexed_count = self._index_documents(documents, vehicle)

        retrieval_query = " ".join(
            part
            for part in (
                retrieval_question,
                vehicle["manufacturer"],
                vehicle["model"],
                str(vehicle["year"]),
                vehicle["fuel_type"],
                vehicle.get("engine") or "",
                vehicle.get("market") or "",
            )
            if part
        )
        retrieved = self.retrieval.retrieve(
            query=retrieval_query,
            vehicle=vehicle,
            limit=settings.rag_retrieval_limit,
        )
        reranked = self.reranker.rerank(
            retrieval_query,
            retrieved,
            top_k=settings.rag_result_limit,
        )
        context, sources = self._build_answer_context(reranked)
        vehicle_description = ", ".join(
            part
            for part in (
                vehicle["manufacturer"],
                vehicle["model"],
                str(vehicle["year"]),
                vehicle["fuel_type"],
                vehicle.get("engine") or "",
                vehicle.get("market") or "",
            )
            if part
        )
        if assistant_instructions:
            answer = self.answer_generator.generate_answer(
                question=question,
                context=context,
                vehicle_context=vehicle_description,
                assistant_instructions=assistant_instructions,
            )
        else:
            answer = self.answer_generator.generate_answer(
                question=question,
                context=context,
                vehicle_context=vehicle_description,
            )
        answer = self._validate_answer_citations(answer, sources)

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "documents_retrieved": len(retrieved),
            "documents_indexed": indexed_count,
            "generated_at": datetime.now(timezone.utc),
        }
