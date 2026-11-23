import unittest
from tempfile import TemporaryDirectory

from app.core.config import settings
from app.services.rag.vector_store import VectorStore
from unittest.mock import patch


class RAGVectorStoreTests(unittest.TestCase):
    def test_cache_and_retrieval_are_scoped_to_vehicle_profile(self):
        source = {
            "title": "Synthetic maintenance source",
            "url": "https://example.test/maintenance",
            "source_type": "web",
            "source_priority": 1,
            "content": "Synthetic text used only in an isolated vector store.",
        }
        vehicle = {
            "id": 41,
            "manufacturer": "Example",
            "model": "Test vehicle",
            "year": 2020,
            "fuel_type": "petrol",
            "engine": None,
            "market": None,
        }
        other_vehicle = {**vehicle, "id": 42}

        with TemporaryDirectory() as directory:
            with patch.object(
                settings,
                "chroma_persist_directory",
                directory,
            ):
                store = VectorStore()
                try:
                    count = store.store_documents(
                        chunks=["synthetic maintenance interval"],
                        embeddings=[[1.0, 0.0, 0.0]],
                        source=source,
                        vehicle=vehicle,
                    )
                    self.assertEqual(count, 1)
                    self.assertTrue(
                        store.refresh_cached_source(source, vehicle)
                    )

                    vehicle_key = store._context_key(vehicle)
                    vehicle_results = store.search(
                        query_embedding=[1.0, 0.0, 0.0],
                        vehicle_id=vehicle["id"],
                        context_key=vehicle_key,
                        limit=5,
                    )
                    self.assertEqual(
                        vehicle_results["documents"][0],
                        ["synthetic maintenance interval"],
                    )

                    other_results = store.search(
                        query_embedding=[1.0, 0.0, 0.0],
                        vehicle_id=other_vehicle["id"],
                        context_key=store._context_key(other_vehicle),
                        limit=5,
                    )
                    self.assertEqual(other_results["documents"], [[]])
                finally:
                    store.close()


if __name__ == "__main__":
    unittest.main()
