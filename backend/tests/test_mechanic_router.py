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
from app.models import (
    DiagnosticMessage,
    DiagnosticSession,
    User,
    Vehicle,
)
from app.routers.mechanic import router
from app.services.rag.errors import RAGProviderError
from app.services.rag.dependencies import get_rag_service


class FakeRAGService:
    def __init__(self):
        self.calls = []
        self.fail = False

    def ask(
        self,
        question,
        vehicle,
        assistant_instructions,
        search_query,
    ):
        self.calls.append(
            {
                "question": question,
                "vehicle": vehicle,
                "assistant_instructions": assistant_instructions,
                "search_query": search_query,
            }
        )
        if self.fail:
            raise RAGProviderError("Synthetic provider failure")
        return {
            "answer": "A starting-circuit issue is possible; check the manual.",
            "sources": [
                {
                    "source_id": "S1",
                    "title": "Synthetic source",
                    "url": "https://example.test/maintenance",
                    "source_type": "web",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }


class MechanicRouterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        db = Session(self.engine)
        owner = User(email="owner@example.com", hashed_password="test-hash")
        other = User(email="other@example.com", hashed_password="test-hash")
        db.add_all([owner, other])
        db.flush()
        self.owner_id = owner.id

        owner_vehicle = Vehicle(
            user_id=owner.id,
            vehicle_name="Owner vehicle",
            manufacturer="Example",
            model="Roadster",
            year=2020,
            fuel_type="petrol",
            registration_number="MECH-OWNER-1",
        )
        other_vehicle = Vehicle(
            user_id=other.id,
            vehicle_name="Other vehicle",
            manufacturer="Example",
            model="Roadster",
            year=2020,
            fuel_type="petrol",
            registration_number="MECH-OTHER-1",
        )
        db.add_all([owner_vehicle, other_vehicle])
        db.flush()
        self.vehicle_id = owner_vehicle.id
        self.other_vehicle_id = other_vehicle.id

        other_session = DiagnosticSession(
            user_id=other.id,
            vehicle_id=other_vehicle.id,
            title="Private diagnostic",
        )
        db.add(other_session)
        db.flush()
        self.other_session_id = other_session.id
        db.add(
            DiagnosticMessage(
                session_id=other_session.id,
                role="user",
                content="Private vehicle symptom",
            )
        )
        db.commit()
        db.close()

        self.rag_service = FakeRAGService()
        app = FastAPI()
        app.include_router(router)

        def override_get_db():
            session = Session(self.engine)
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=self.owner_id
        )
        app.dependency_overrides[get_rag_service] = lambda: self.rag_service
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_new_session_continuation_and_history_retrieval(self):
        path = f"/mechanic/vehicles/{self.vehicle_id}/ask"
        first = self.client.post(
            path,
            json={"question": "My starter makes a clicking sound."},
        )
        self.assertEqual(first.status_code, 200)
        session_id = first.json()["session_id"]
        self.assertEqual(first.json()["sources"][0]["source_id"], "S1")
        self.assertEqual(len(self.rag_service.calls), 1)

        second = self.client.post(
            path,
            json={
                "question": "The engine does not start and the light dims.",
                "session_id": session_id,
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertIn(
            "starter makes a clicking sound",
            self.rag_service.calls[1]["question"],
        )
        self.assertIn(
            "starter makes a clicking sound",
            self.rag_service.calls[1]["search_query"],
        )

        sessions = self.client.get(
            f"/mechanic/vehicles/{self.vehicle_id}/sessions"
        )
        self.assertEqual(sessions.status_code, 200)
        self.assertEqual([row["id"] for row in sessions.json()], [session_id])

        messages = self.client.get(
            f"/mechanic/sessions/{session_id}/messages"
        )
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(
            [message["role"] for message in messages.json()],
            ["user", "assistant", "user", "assistant"],
        )

    def test_ownership_is_enforced_for_vehicle_and_session_reads(self):
        foreign_ask = self.client.post(
            f"/mechanic/vehicles/{self.other_vehicle_id}/ask",
            json={"question": "The engine makes a noise."},
        )
        self.assertEqual(foreign_ask.status_code, 404)
        self.assertEqual(len(self.rag_service.calls), 0)

        foreign_sessions = self.client.get(
            f"/mechanic/vehicles/{self.other_vehicle_id}/sessions"
        )
        self.assertEqual(foreign_sessions.status_code, 404)

        foreign_messages = self.client.get(
            f"/mechanic/sessions/{self.other_session_id}/messages"
        )
        self.assertEqual(foreign_messages.status_code, 404)

    def test_session_cannot_be_reused_for_another_vehicle(self):
        first = self.client.post(
            f"/mechanic/vehicles/{self.vehicle_id}/ask",
            json={"question": "My starter makes a clicking sound."},
        )
        session_id = first.json()["session_id"]
        wrong_vehicle = self.client.post(
            f"/mechanic/vehicles/{self.other_vehicle_id}/ask",
            json={
                "question": "The engine does not start.",
                "session_id": session_id,
            },
        )
        self.assertEqual(wrong_vehicle.status_code, 404)

    def test_urgent_symptom_gets_safety_response_without_rag(self):
        response = self.client.post(
            f"/mechanic/vehicles/{self.vehicle_id}/ask",
            json={"question": "My brakes have failed while driving."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("do not continue driving", response.json()["answer"])
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(self.rag_service.calls, [])

    def test_rag_failure_keeps_user_message_for_retry(self):
        self.rag_service.fail = True
        response = self.client.post(
            f"/mechanic/vehicles/{self.vehicle_id}/ask",
            json={"question": "My starter makes a clicking sound."},
        )
        self.assertEqual(response.status_code, 503)

        db = Session(self.engine)
        try:
            session = (
                db.query(DiagnosticSession)
                .filter(DiagnosticSession.user_id == self.owner_id)
                .one()
            )
            messages = (
                db.query(DiagnosticMessage)
                .filter(DiagnosticMessage.session_id == session.id)
                .all()
            )
            self.assertEqual(
                [(message.role, message.content) for message in messages],
                [("user", "My starter makes a clicking sound.")],
            )
        finally:
            db.close()

    def test_blank_question_is_rejected(self):
        response = self.client.post(
            f"/mechanic/vehicles/{self.vehicle_id}/ask",
            json={"question": "   "},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.rag_service.calls, [])


if __name__ == "__main__":
    unittest.main()
