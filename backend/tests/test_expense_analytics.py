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
from app.models import Expense, ServiceRecord, User, Vehicle
from app.routers.analytics import router


class ExpenseAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        owner = User(email="owner@example.com", hashed_password="test-hash")
        other = User(email="other@example.com", hashed_password="test-hash")
        self.db.add_all([owner, other])
        self.db.flush()
        self.owner_id = owner.id

        owned = Vehicle(
            user_id=owner.id,
            vehicle_name="Owned car",
            manufacturer="Test",
            model="Model",
            year=2020,
            fuel_type="petrol",
            registration_number="OWNED-001",
        )
        other_vehicle = Vehicle(
            user_id=other.id,
            vehicle_name="Foreign car",
            manufacturer="Test",
            model="Model",
            year=2020,
            fuel_type="petrol",
            registration_number="FOREIGN-001",
        )
        empty_vehicle = Vehicle(
            user_id=owner.id,
            vehicle_name="Empty car",
            manufacturer="Test",
            model="Model",
            year=2021,
            fuel_type="diesel",
            registration_number="EMPTY-001",
        )
        self.db.add_all([owned, other_vehicle, empty_vehicle])
        self.db.flush()
        self.vehicle_id = owned.id
        self.other_vehicle_id = other_vehicle.id
        self.empty_vehicle_id = empty_vehicle.id

        service = ServiceRecord(
            vehicle_id=owned.id,
            service_date=date(2026, 1, 15),
            odometer_reading=10000,
            service_type="Oil change",
            total_cost=2500,
        )
        self.db.add(service)
        self.db.flush()

        self.db.add_all([
            Expense(
                vehicle_id=owned.id,
                service_record_id=service.id,
                category="Engine oil",
                amount=2500,
                expense_date=date(2026, 1, 15),
            ),
            Expense(
                vehicle_id=owned.id,
                service_record_id=None,
                category="Fuel",
                amount=4000,
                expense_date=date(2026, 1, 20),
            ),
            Expense(
                vehicle_id=owned.id,
                service_record_id=None,
                category="Tyres",
                amount=6000,
                expense_date=date(2026, 2, 10),
            ),
            Expense(
                vehicle_id=owned.id,
                service_record_id=None,
                category="Fuel",
                amount=1500,
                expense_date=date(2025, 12, 10),
            ),
        ])
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
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_summary_category_monthly_yearly_and_services(self):
        summary = self.client.get(
            f"/analytics/vehicles/{self.vehicle_id}/summary"
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["total_expenses"], 14000)
        self.assertEqual(summary.json()["total_transactions"], 4)
        self.assertEqual(summary.json()["average_expense"], 3500)

        categories = self.client.get(
            f"/analytics/vehicles/{self.vehicle_id}/categories"
        ).json()
        self.assertEqual(categories[0]["category"], "Tyres")
        fuel = next(row for row in categories if row["category"] == "Fuel")
        self.assertEqual(fuel["total_amount"], 5500)
        self.assertEqual(fuel["transaction_count"], 2)

        monthly = self.client.get(
            f"/analytics/vehicles/{self.vehicle_id}/monthly"
        ).json()
        self.assertIn(
            {"year": 2026, "month": 1, "total_amount": 6500},
            monthly,
        )
        yearly = self.client.get(
            f"/analytics/vehicles/{self.vehicle_id}/yearly"
        ).json()
        self.assertIn(
            {"year": 2026, "total_amount": 12500},
            yearly,
        )

        services = self.client.get(
            f"/analytics/vehicles/{self.vehicle_id}/services"
        ).json()
        oil = next(
            row for row in services
            if row["service_type"] == "Oil change"
        )
        self.assertEqual(oil["total_amount"], 2500)
        unlinked = next(
            row for row in services
            if row["service_type"] == "Unlinked / not specified"
        )
        self.assertEqual(unlinked["total_amount"], 11500)

    def test_vehicle_comparison_and_ownership(self):
        comparison = self.client.get(
            "/analytics/expenses/comparison"
        )
        self.assertEqual(comparison.status_code, 200)
        rows = comparison.json()
        owned = next(
            row for row in rows
            if row["vehicle_id"] == self.vehicle_id
        )
        empty = next(
            row for row in rows
            if row["vehicle_id"] == self.empty_vehicle_id
        )
        self.assertEqual(owned["total_expenses"], 14000)
        self.assertEqual(empty["total_expenses"], 0)
        self.assertFalse(
            any(row["vehicle_id"] == self.other_vehicle_id for row in rows)
        )

        foreign = self.client.get(
            f"/analytics/vehicles/{self.other_vehicle_id}/summary"
        )
        self.assertEqual(foreign.status_code, 404)

    def test_service_analytics_rejects_cross_vehicle_service_link(self):
        foreign_service = ServiceRecord(
            vehicle_id=self.other_vehicle_id,
            service_date=date(2026, 3, 1),
            odometer_reading=20000,
            service_type="Foreign brake service",
        )
        self.db.add(foreign_service)
        self.db.flush()
        self.db.add(
            Expense(
                vehicle_id=self.vehicle_id,
                service_record_id=foreign_service.id,
                category="Repairs",
                amount=800,
                expense_date=date(2026, 3, 1),
            )
        )
        self.db.commit()

        services = self.client.get(
            f"/analytics/vehicles/{self.vehicle_id}/services"
        ).json()
        unlinked = next(
            row for row in services
            if row["service_type"] == "Unlinked / not specified"
        )
        self.assertEqual(unlinked["total_amount"], 12300)
        self.assertFalse(
            any(
                row["service_type"] == "Foreign brake service"
                for row in services
            )
        )


if __name__ == "__main__":
    unittest.main()
