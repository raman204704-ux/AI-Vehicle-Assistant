import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.database.connection import Base, get_db
from app.models import User, Vehicle
from app.routers.assistant import get_rag_service, router
from app.services.rag.errors import RAGConfigurationError


class FakeRAGService:
    def __init__(self, fail=False):
        self.fail = fail
        self.called = False

    def ask(self, question, vehicle):
        self.called = True
        if self.fail:
            raise RAGConfigurationError("TAVILY_API_KEY is not configured")
        return {
            "question": question,
            "answer": "Insufficient evidence for a specific interval.",
            "sources": [
                {
                    "source_id": "S1",
                    "title": "Synthetic source",
                    "url": "https://example.test/maintenance",
                    "source_type": "web",
                    "retrieved_at": datetime.now(timezone.utc),
                }
            ],
            "documents_retrieved": 1,
            "documents_indexed": 0,
            "generated_at": datetime.now(timezone.utc),
        }


class AssistantRouterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        session = Session(self.engine)
        owner = User(email="owner@example.com", hashed_password="test-hash")
        other = User(email="other@example.com", hashed_password="test-hash")
        session.add_all([owner, other])
        session.flush()
        self.owner_id = owner.id
        self.vehicle = Vehicle(
            user_id=owner.id,
            vehicle_name="Owner vehicle",
            manufacturer="Tata",
            model="Zest",
            year=2015,
            fuel_type="Diesel",
            registration_number="OWNER-RAG-1",
        )
        other_vehicle = Vehicle(
            user_id=other.id,
            vehicle_name="Other vehicle",
            manufacturer="Tata",
            model="Zest",
            year=2015,
            fuel_type="Diesel",
            registration_number="OTHER-RAG-1",
        )
        session.add_all([self.vehicle, other_vehicle])
        session.commit()
        self.vehicle_id = self.vehicle.id
        self.other_vehicle_id = other_vehicle.id
        session.close()

        self.service = FakeRAGService()
        app = FastAPI()
        app.include_router(router)

        def override_get_db():
            db = Session(self.engine)
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=self.owner_id
        )
        app.dependency_overrides[get_rag_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_owner_can_ask_and_vehicle_context_is_forwarded(self):
        response = self.client.post(
            f"/assistant/vehicles/{self.vehicle_id}/ask",
            json={
                "question": "When should I replace engine oil?",
                "engine": "1.3L Diesel",
                "market": "India",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"][0]["source_id"], "S1")
        self.assertTrue(self.service.called)

    def test_non_owner_gets_not_found_without_rag_request(self):
        response = self.client.post(
            f"/assistant/vehicles/{self.other_vehicle_id}/ask",
            json={"question": "When should I replace engine oil?"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.service.called)

    def test_provider_configuration_error_is_explicit(self):
        self.service.fail = True
        response = self.client.post(
            f"/assistant/vehicles/{self.vehicle_id}/ask",
            json={"question": "When should I replace engine oil?"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "TAVILY_API_KEY is not configured",
        )


if __name__ == "__main__":
    unittest.main()
