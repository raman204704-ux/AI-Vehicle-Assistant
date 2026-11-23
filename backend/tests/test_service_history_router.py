import unittest
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.database.connection import Base, get_db
from app.models import ServiceRecord, User, Vehicle
from app.routers.service_history import router


class ServiceHistoryRouterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        db = Session(self.engine)

        owner = User(email="owner@example.com", hashed_password="test-hash")
        other_user = User(
            email="other@example.com",
            hashed_password="test-hash",
        )
        db.add_all([owner, other_user])
        db.flush()
        self.owner_id = owner.id

        vehicle = Vehicle(
            user_id=owner.id,
            vehicle_name="Owner vehicle",
            manufacturer="Test",
            model="Model",
            year=2020,
            fuel_type="petrol",
            registration_number="OWNER-001",
        )
        other_vehicle = Vehicle(
            user_id=other_user.id,
            vehicle_name="Other vehicle",
            manufacturer="Test",
            model="Model",
            year=2020,
            fuel_type="petrol",
            registration_number="OTHER-001",
        )
        db.add_all([vehicle, other_vehicle])
        db.flush()
        self.vehicle_id = vehicle.id
        self.other_vehicle_id = other_vehicle.id

        foreign_record = ServiceRecord(
            vehicle_id=other_vehicle.id,
            service_date=date(2026, 10, 10),
            odometer_reading=12000,
            service_type="Oil change",
        )
        db.add(foreign_record)
        db.commit()
        self.foreign_record_id = foreign_record.id
        db.close()

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
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_create_list_update_and_delete(self):
        path = f"/vehicles/{self.vehicle_id}/service-records"
        payload = {
            "service_date": "2026-11-15",
            "odometer_reading": 12000,
            "service_type": "Oil change",
            "description": "Engine oil replacement",
            "total_cost": 1000,
        }

        created = self.client.post(path, json=payload)
        self.assertEqual(created.status_code, 201)
        record = created.json()
        self.assertEqual(record["source_type"], "manual")
        self.assertIsNone(record["source_document_id"])

        duplicate = self.client.post(path, json=payload)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(
            duplicate.json()["detail"]["existing_record_id"],
            record["id"],
        )

        listed = self.client.get(path)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()], [record["id"]])

        updated = self.client.put(
            f"/service-records/{record['id']}",
            json={"total_cost": 1250},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["total_cost"], 1250)

        deleted = self.client.delete(f"/service-records/{record['id']}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get(f"/service-records/{record['id']}").status_code,
            404,
        )

    def test_duplicate_update_and_foreign_records_are_rejected(self):
        path = f"/vehicles/{self.vehicle_id}/service-records"
        first = self.client.post(
            path,
            json={
                "service_date": "2026-10-10",
                "odometer_reading": 12000,
                "service_type": "Oil change",
            },
        )
        second = self.client.post(
            path,
            json={
                "service_date": "2026-11-10",
                "odometer_reading": 13000,
                "service_type": "Brake repair",
            },
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        duplicate_update = self.client.put(
            f"/service-records/{second.json()['id']}",
            json={
                "service_date": "2026-10-10",
                "odometer_reading": 12000,
                "service_type": "OIL CHANGE",
            },
        )
        self.assertEqual(duplicate_update.status_code, 409)

        self.assertEqual(
            self.client.get(
                f"/vehicles/{self.other_vehicle_id}/service-records"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/service-records/{self.foreign_record_id}"
            ).status_code,
            404,
        )

    def test_create_rejects_provenance_fields_and_invalid_values(self):
        path = f"/vehicles/{self.vehicle_id}/service-records"
        payload = {
            "service_date": "2026-11-15",
            "odometer_reading": 12000,
            "service_type": "Oil change",
            "source_type": "invoice",
            "source_document_id": 10,
        }

        response = self.client.post(path, json=payload)
        self.assertEqual(response.status_code, 422)

        payload.pop("source_type")
        payload.pop("source_document_id")
        payload["odometer_reading"] = -1
        response = self.client.post(path, json=payload)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
