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
from app.models import MaintenanceRule, ServiceRecord, User, Vehicle
from app.routers.maintenance import router
from app.services.maintenance_prediction_service import (
    calculate_prediction,
    get_applicable_rules,
    get_last_service,
)


def make_rule(**overrides):
    values = {
        "maintenance_type": "Oil service",
        "service_type": "Oil change",
        "source_title": "Synthetic test rule",
        "source_url": "https://example.test/maintenance",
        "verified_at": date(2026, 1, 1),
        "interval_km": 5000,
        "interval_months": None,
    }
    values.update(overrides)
    return MaintenanceRule(**values)


class MaintenancePredictionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        owner = User(email="owner@example.com", hashed_password="test-hash")
        other_user = User(
            email="other@example.com",
            hashed_password="test-hash",
        )
        self.db.add_all([owner, other_user])
        self.db.flush()
        self.owner_id = owner.id

        self.vehicle = Vehicle(
            user_id=owner.id,
            vehicle_name="Test car",
            manufacturer="Example",
            model="Roadster",
            year=2020,
            fuel_type="petrol",
            registration_number="TEST-001",
            current_odometer=10400,
        )
        other_vehicle = Vehicle(
            user_id=other_user.id,
            vehicle_name="Other car",
            manufacturer="Example",
            model="Roadster",
            year=2020,
            fuel_type="petrol",
            registration_number="TEST-002",
        )
        self.db.add_all([self.vehicle, other_vehicle])
        self.db.commit()
        self.vehicle_id = self.vehicle.id
        self.other_vehicle_id = other_vehicle.id

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_rules_filter_by_vehicle_and_effective_date(self):
        matching = make_rule(
            manufacturer=" example ",
            model="ROADSTER",
            fuel_type="PETROL",
            model_year_min=2018,
            model_year_max=2022,
        )
        future = make_rule(effective_date=date(2026, 2, 1))
        wrong_manufacturer = make_rule(manufacturer="Other")
        wrong_year = make_rule(model_year_min=2021)
        inactive = make_rule(is_active=False)
        self.db.add_all(
            [matching, future, wrong_manufacturer, wrong_year, inactive]
        )
        self.db.commit()

        applicable = get_applicable_rules(
            self.db,
            self.vehicle,
            as_of=date(2026, 1, 31),
        )

        self.assertEqual([rule.id for rule in applicable], [matching.id])

    def test_latest_service_matches_trimmed_case_insensitive_type(self):
        older = ServiceRecord(
            vehicle_id=self.vehicle_id,
            service_date=date(2025, 1, 1),
            odometer_reading=5000,
            service_type="Oil change",
        )
        latest = ServiceRecord(
            vehicle_id=self.vehicle_id,
            service_date=date(2025, 6, 1),
            odometer_reading=7000,
            service_type=" oil CHANGE ",
        )
        unrelated = ServiceRecord(
            vehicle_id=self.vehicle_id,
            service_date=date(2025, 12, 1),
            odometer_reading=9000,
            service_type="Brake service",
        )
        self.db.add_all([older, latest, unrelated])
        self.db.commit()

        result = get_last_service(
            self.db,
            self.vehicle_id,
            "Oil change",
        )

        self.assertEqual(result.id, latest.id)

    def test_distance_and_time_status_priority_and_month_end(self):
        last_service = SimpleNamespace(
            service_date=date(2026, 1, 31),
            odometer_reading=10000,
        )
        rule = make_rule(interval_km=5000, interval_months=1)

        prediction = calculate_prediction(
            rule,
            last_service,
            current_odometer=14600,
            today=date(2026, 2, 1),
        )

        self.assertEqual(prediction["next_due_date"], date(2026, 2, 28))
        self.assertEqual(prediction["remaining_days"], 27)
        self.assertEqual(prediction["remaining_km"], 400)
        self.assertEqual(prediction["status"], "due_soon")

        overdue_rule = make_rule(interval_km=5000, interval_months=12)
        overdue = calculate_prediction(
            overdue_rule,
            SimpleNamespace(
                service_date=date(2025, 1, 31),
                odometer_reading=10000,
            ),
            current_odometer=10000,
            today=date(2026, 2, 1),
        )
        self.assertEqual(overdue["status"], "overdue")

        unknown_distance = SimpleNamespace(
            service_date=date(2026, 1, 31),
            odometer_reading=15000,
        )
        unknown_over_due_soon = calculate_prediction(
            rule,
            unknown_distance,
            current_odometer=10000,
            today=date(2026, 2, 1),
        )
        self.assertEqual(unknown_over_due_soon["status"], "unknown")

        overdue_over_unknown = calculate_prediction(
            overdue_rule,
            SimpleNamespace(
                service_date=date(2025, 1, 31),
                odometer_reading=15000,
            ),
            current_odometer=10000,
            today=date(2026, 2, 1),
        )
        self.assertEqual(overdue_over_unknown["status"], "overdue")

    def test_missing_history_and_lower_odometer_are_unknown(self):
        distance_rule = make_rule(interval_km=5000)
        missing = calculate_prediction(
            distance_rule,
            None,
            current_odometer=10000,
            today=date(2026, 1, 1),
        )
        self.assertEqual(missing["status"], "unknown")

        last_service = SimpleNamespace(
            service_date=date(2025, 1, 1),
            odometer_reading=11000,
        )
        inconsistent = calculate_prediction(
            distance_rule,
            last_service,
            current_odometer=10000,
            today=date(2026, 1, 1),
        )
        self.assertEqual(inconsistent["status"], "unknown")

    def test_endpoint_returns_predictions_only_for_owned_vehicle(self):
        self.db.add(make_rule(interval_km=5000))
        self.db.commit()

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
        client = TestClient(app)
        try:
            response = client.get(
                f"/maintenance/vehicles/{self.vehicle_id}/predictions"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["vehicle_id"], self.vehicle_id)
            self.assertEqual(len(response.json()["predictions"]), 1)

            foreign = client.get(
                f"/maintenance/vehicles/{self.other_vehicle_id}/predictions"
            )
            self.assertEqual(foreign.status_code, 404)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
