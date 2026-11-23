import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.rag.chunking import TextChunker
from app.services.rag.answer_generator import AnswerGenerator, NO_EVIDENCE_ANSWER
from app.services.rag.reranker import Reranker
from app.services.rag.rag_service import (
    CITATION_VALIDATION_FALLBACK,
    RAGService,
)
from app.services.rag.web_search import WebSearchService
from app.services.rag.errors import RAGConfigurationError
from app.schemas.assistant import VehicleQuestion
from app.core.config import settings
from pydantic import SecretStr


class FakeSearch:
    def __init__(self):
        self.query = None
        self.queries = []

    def search(self, query):
        self.query = query
        return [
            {
                "title": "Official maintenance schedule",
                "url": "https://support.tatamotors.com/maintenance",
                "content": "Engine oil replacement information. " * 15,
                "score": 0.9,
            },
            {
                "title": "Different vehicle",
                "url": "https://example.org/vehicle",
                "content": "General vehicle information. " * 15,
                "score": 0.8,
            },
            {
                "title": "Unsafe local address",
                "url": "http://127.0.0.1/admin",
                "content": "This must never be indexed. " * 15,
                "score": 1.0,
            },
        ]

    def search_many(self, queries):
        self.queries = queries
        results = []
        for query in queries:
            results.extend(self.search(query))
        return results

    def extract(self, urls):
        raise AssertionError("Search results already contained sufficient text")


class FakeExtractor:
    def extract(self, result):
        return {
            "title": result["title"],
            "url": result["url"],
            "content": result["content"],
            "score": result["score"],
            "host": result["url"].split("/")[2],
        }


class FakeVectorStore:
    def __init__(self):
        self.indexed = []

    def refresh_cached_source(self, source, vehicle):
        return False

    def store_documents(self, chunks, embeddings, source, vehicle):
        self.indexed.append((chunks, source, vehicle))
        return len(chunks)


class FakeEmbeddings:
    def generate_embeddings(self, texts):
        return [[0.1, 0.2] for _ in texts]


class FakeRetrieval:
    def retrieve(self, query, vehicle, limit):
        self.query = query
        return [
            {
                "content": "Use the vehicle-specific service schedule.",
                "metadata": {
                    "source_url": "https://support.tatamotors.com/maintenance",
                    "source_title": "Official maintenance schedule",
                    "source_type": "manufacturer",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "source_priority": 3,
                },
                "distance": 0.1,
            }
        ]


class FakeReranker:
    def rerank(self, query, documents, top_k):
        return documents[:top_k]


class FakeAnswerGenerator:
    def generate_answer(self, question, context, vehicle_context):
        self.context = context
        self.vehicle_context = vehicle_context
        return "Consult the applicable schedule [S1]."


class RAGServiceTests(unittest.TestCase):
    def test_chunker_uses_overlapping_word_windows(self):
        chunker = TextChunker(chunk_size=4, overlap=1)

        chunks = chunker.split_text("one two three four five six seven")

        self.assertEqual(chunks, ["one two three four", "four five six seven"])

    def test_chunker_rejects_invalid_overlap(self):
        with self.assertRaises(ValueError):
            TextChunker(chunk_size=4, overlap=4)

    def test_search_requires_configured_tavily_key(self):
        with patch.object(settings, "tavily_api_key", None):
            with self.assertRaisesRegex(
                RAGConfigurationError,
                "TAVILY_API_KEY is not configured",
            ):
                WebSearchService().search("synthetic query")

    def test_search_passes_vehicle_specific_query_to_tavily(self):
        with (
            patch.object(settings, "tavily_api_key", SecretStr("test-key")),
            patch("tavily.TavilyClient") as client_class,
        ):
            client_class.return_value.search.return_value = {
                "results": [{"url": "https://example.test"}]
            }
            results = WebSearchService().search(
                "Tata Zest XT 2015 Diesel engine oil maintenance"
            )

        self.assertEqual(len(results), 1)
        client_class.return_value.search.assert_called_once_with(
            query="Tata Zest XT 2015 Diesel engine oil maintenance",
            search_depth="advanced",
            max_results=settings.rag_max_search_results,
            include_raw_content=True,
        )

    def test_search_many_deduplicates_urls_across_targeted_queries(self):
        with (
            patch.object(settings, "tavily_api_key", SecretStr("test-key")),
            patch("tavily.TavilyClient") as client_class,
        ):
            client_class.return_value.search.side_effect = [
                {
                    "results": [
                        {"url": "https://example.org/one"},
                        {"url": "https://example.org/shared"},
                    ]
                },
                {
                    "results": [
                        {"url": "https://example.org/shared"},
                        {"url": "https://example.org/two"},
                    ]
                },
            ]
            results = WebSearchService().search_many(["official query", "broad query"])

        self.assertEqual(
            [result["url"] for result in results],
            [
                "https://example.org/one",
                "https://example.org/shared",
                "https://example.org/two",
            ],
        )
        self.assertEqual(client_class.return_value.search.call_count, 2)

    def test_answer_generator_returns_safe_fallback_without_evidence(self):
        with patch.object(settings, "groq_api_key", None):
            answer = AnswerGenerator().generate_answer(
                question="When is service due?",
                context="",
                vehicle_context="Synthetic test vehicle",
            )

        self.assertEqual(answer, NO_EVIDENCE_ANSWER)

    def test_reranker_blends_relevance_and_reliability(self):
        class FakeModel:
            def predict(self, pairs, show_progress_bar):
                return [0.2, -0.5]

        reranker = Reranker()
        reranker._model = FakeModel()
        documents = [
            {
                "content": "Manufacturer evidence",
                "metadata": {"source_priority": 3},
            },
            {
                "content": "General web evidence",
                "metadata": {"source_priority": 1},
            },
        ]

        ranked = reranker.rerank("question", documents, top_k=2)

        self.assertEqual(ranked[0]["metadata"]["source_priority"], 3)

    def test_reranker_allows_stronger_relevance_to_outweigh_source_priority(self):
        class FakeModel:
            def predict(self, pairs, show_progress_bar):
                return [-2.0, 4.0]

        reranker = Reranker()
        reranker._model = FakeModel()
        documents = [
            {
                "content": "Weakly relevant official evidence",
                "metadata": {"source_priority": 5},
            },
            {
                "content": "Highly relevant general evidence",
                "metadata": {"source_priority": 1},
            },
        ]

        ranked = reranker.rerank("question", documents, top_k=2)

        self.assertEqual(ranked[0]["content"], "Highly relevant general evidence")

    def test_pipeline_indexes_vehicle_specific_sources_and_cites_them(self):
        service = RAGService()
        service.web_search = FakeSearch()
        service.extractor = FakeExtractor()
        service.vector_store = FakeVectorStore()
        service.embedding_service = FakeEmbeddings()
        service.chunker = TextChunker(chunk_size=12, overlap=2)
        service.retrieval = FakeRetrieval()
        service.reranker = FakeReranker()
        answer_generator = FakeAnswerGenerator()
        service.answer_generator = answer_generator
        vehicle = {
            "id": 7,
            "manufacturer": "Tata",
            "model": "Zest XT",
            "year": 2015,
            "fuel_type": "Diesel",
            "engine": "1.3L",
            "market": "India",
        }

        result = service.ask("When should I replace engine oil?", vehicle)

        self.assertIn(
            "Tata Zest XT 2015 Diesel 1.3L India",
            service.web_search.query,
        )
        self.assertTrue(
            any(query.startswith("site:tatamotors.com") for query in service.web_search.queries)
        )
        self.assertEqual(result["documents_retrieved"], 1)
        self.assertGreater(result["documents_indexed"], 0)
        self.assertEqual(len(service.vector_store.indexed), 2)
        self.assertTrue(
            all(
                item[1]["source_type"] == "manufacturer_documentation"
                for item in service.vector_store.indexed[:1]
            )
        )
        self.assertEqual(
            result["sources"][0]["source_type"],
            "manufacturer",
        )
        self.assertIn("[S1]", result["answer"])
        self.assertIn("Tata, Zest XT, 2015, Diesel, 1.3L, India", answer_generator.vehicle_context)

    def test_non_public_urls_are_rejected(self):
        self.assertFalse(RAGService._is_public_source_url("file:///etc/passwd"))
        self.assertFalse(RAGService._is_public_source_url("http://localhost/page"))
        self.assertFalse(RAGService._is_public_source_url("http://10.0.0.5/page"))
        self.assertTrue(
            RAGService._is_public_source_url(
                "https://support.tatamotors.com/maintenance"
            )
        )

    def test_source_quality_uses_granular_domain_categories(self):
        self.assertEqual(
            RAGService._source_quality(
                "support.tatamotors.com",
                "Tata Motors",
                "Official maintenance schedule",
            ),
            (5, "manufacturer_documentation"),
        )
        self.assertEqual(
            RAGService._source_quality("tata.example.org", "Tata"),
            (1, "unverified_web"),
        )
        self.assertEqual(
            RAGService._source_quality("transport.gov.in", "Tata"),
            (4, "government"),
        )
        self.assertEqual(
            RAGService._source_quality("spinny.com", "Tata"),
            (3, "reputable_automotive_publication"),
        )
        self.assertEqual(
            RAGService._source_quality("cars.example.org", "Tata"),
            (2, "general_automotive_website"),
        )

    def test_search_queries_target_manufacturer_and_keep_broad_fallback(self):
        vehicle = {
            "manufacturer": "Tata Motors",
            "model": "Zest",
            "year": 2015,
            "fuel_type": "Diesel",
        }

        queries = RAGService._build_search_queries(
            "engine oil interval",
            vehicle,
        )

        self.assertTrue(queries[0].startswith("site:tatamotors.com"))
        self.assertIn("owner manual maintenance schedule", queries[0])
        self.assertNotIn("site:", queries[-1])

    def test_search_queries_use_explicit_official_terms_for_unknown_manufacturer(self):
        vehicle = {
            "manufacturer": "Acme Motors",
            "model": "Roadster",
            "year": 2022,
            "fuel_type": "Electric",
        }

        queries = RAGService._build_search_queries("battery service", vehicle)

        self.assertIn("official Acme Motors owner manual", queries[0])
        self.assertNotIn("site:", queries[0])

    def test_citation_validation_accepts_only_supplied_source_ids(self):
        sources = [{"source_id": "S1"}]
        valid_answer = "Consult the applicable schedule [S1]."

        self.assertEqual(
            RAGService._validate_answer_citations(valid_answer, sources),
            valid_answer,
        )
        self.assertEqual(
            RAGService._validate_answer_citations(
                "Replace coolant at 40,000 km [S5].",
                sources,
            ),
            CITATION_VALIDATION_FALLBACK,
        )
        self.assertEqual(
            RAGService._validate_answer_citations(
                "Replace coolant at 40,000 km.",
                sources,
            ),
            CITATION_VALIDATION_FALLBACK,
        )

    def test_question_schema_trims_and_rejects_blank_input(self):
        parsed = VehicleQuestion(question="  Engine oil interval?  ")
        self.assertEqual(parsed.question, "Engine oil interval?")
        with self.assertRaises(ValueError):
            VehicleQuestion(question="     ")


if __name__ == "__main__":
    unittest.main()
