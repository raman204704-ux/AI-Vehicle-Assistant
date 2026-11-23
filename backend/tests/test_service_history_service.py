import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.models import Expense, User, Vehicle
from app.schemas.service_history import (
    ServiceRecordCreate,
    ServiceRecordUpdate,
)
from app.services.service_history_service import (
    create_service_record,
    delete_service_record,
    get_service_record,
    get_user_vehicle,
    get_vehicle_service_history,
    update_service_record,
)


class ServiceHistoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        user = User(email="owner@example.com", hashed_password="test-hash")
        self.db.add(user)
        self.db.flush()
        self.vehicle = Vehicle(
            user_id=user.id,
            vehicle_name="Test Vehicle",
            manufacturer="Test",
            model="Model",
            year=2020,
            fuel_type="petrol",
            registration_number="TEST-001",
        )
        self.db.add(self.vehicle)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_vehicle_lookup_is_scoped_to_user(self):
        self.assertEqual(
            get_user_vehicle(self.db, self.vehicle.id, self.vehicle.user_id),
            self.vehicle,
        )
        self.assertIsNone(
            get_user_vehicle(self.db, self.vehicle.id, self.vehicle.user_id + 1)
        )

    def test_create_history_update_and_delete(self):
        older_result = create_service_record(
            self.db,
            self.vehicle.id,
            ServiceRecordCreate(
                service_date=date(2026, 10, 10),
                odometer_reading=12000,
                service_type="Oil change",
                total_cost=100,
            ),
        )
        newer_result = create_service_record(
            self.db,
            self.vehicle.id,
            ServiceRecordCreate(
                service_date=date(2026, 11, 10),
                odometer_reading=13000,
                service_type="Brake repair",
                total_cost=250,
            ),
        )

        older_record = older_result["record"]
        newer_record = newer_result["record"]
        history = get_vehicle_service_history(self.db, self.vehicle.id)
        self.assertEqual(
            [record.id for record in history],
            [newer_record.id, older_record.id],
        )
        self.assertEqual(older_record.source_type, "manual")
        self.assertIsNone(older_record.source_document_id)
        self.assertEqual(
            get_service_record(
                self.db,
                older_record.id,
                self.vehicle.user_id,
            ).id,
            older_record.id,
        )
        self.assertIsNone(
            get_service_record(
                self.db,
                older_record.id,
                self.vehicle.user_id + 1,
            )
        )

        updated_result = update_service_record(
            self.db,
            older_record,
            ServiceRecordUpdate(
                workshop_name="Local Garage",
                total_cost=125,
            ),
        )
        updated_record = updated_result["record"]
        self.assertEqual(updated_record.workshop_name, "Local Garage")
        self.assertEqual(updated_record.total_cost, 125)
        self.assertEqual(updated_record.source_type, "manual")

        delete_service_record(self.db, newer_record)
        self.assertIsNone(
            get_service_record(
                self.db,
                newer_record.id,
                self.vehicle.user_id,
            )
        )

    def test_create_detects_case_and_whitespace_normalized_duplicates(self):
        data = ServiceRecordCreate(
            service_date=date(2026, 11, 10),
            odometer_reading=13000,
            service_type="Oil change",
        )
        created = create_service_record(self.db, self.vehicle.id, data)
        repeated = create_service_record(
            self.db,
            self.vehicle.id,
            ServiceRecordCreate(
                service_date=data.service_date,
                odometer_reading=data.odometer_reading,
                service_type="OIL CHANGE",
            ),
        )

        self.assertFalse(created["duplicate"])
        self.assertTrue(repeated["duplicate"])
        self.assertEqual(
            repeated["record"].id,
            created["record"].id,
        )
        self.assertEqual(
            len(get_vehicle_service_history(self.db, self.vehicle.id)),
            1,
        )

    def test_update_detects_duplicate_without_changing_record(self):
        first_record = create_service_record(
            self.db,
            self.vehicle.id,
            ServiceRecordCreate(
                service_date=date(2026, 10, 10),
                odometer_reading=12000,
                service_type="Oil change",
            ),
        )["record"]
        second_record = create_service_record(
            self.db,
            self.vehicle.id,
            ServiceRecordCreate(
                service_date=date(2026, 11, 10),
                odometer_reading=13000,
                service_type="Brake repair",
            ),
        )["record"]

        result = update_service_record(
            self.db,
            second_record,
            ServiceRecordUpdate(
                service_date=first_record.service_date,
                odometer_reading=first_record.odometer_reading,
                service_type="OIL CHANGE",
            ),
        )

        self.assertTrue(result["duplicate"])
        self.assertEqual(result["record"].id, first_record.id)
        self.db.refresh(second_record)
        self.assertEqual(second_record.service_type, "Brake repair")

    def test_update_rejects_null_for_required_fields(self):
        record = create_service_record(
            self.db,
            self.vehicle.id,
            ServiceRecordCreate(
                service_date=date(2026, 11, 10),
                odometer_reading=13000,
                service_type="Brake repair",
            ),
        )["record"]

        with self.assertRaises(ValueError):
            update_service_record(
                self.db,
                record,
                ServiceRecordUpdate(service_date=None),
            )

        self.db.refresh(record)
        self.assertEqual(record.service_date, date(2026, 11, 10))

    def test_deleting_record_preserves_and_detaches_expenses(self):
        record = create_service_record(
            self.db,
            self.vehicle.id,
            ServiceRecordCreate(
                service_date=date(2026, 11, 10),
                odometer_reading=13000,
                service_type="Brake repair",
            ),
        )["record"]
        expense = Expense(
            vehicle_id=self.vehicle.id,
            service_record_id=record.id,
            category="labour",
            amount=50,
            expense_date=date(2026, 11, 10),
            description="Repair labour",
        )
        self.db.add(expense)
        self.db.commit()

        delete_service_record(self.db, record)

        self.assertIsNone(
            get_service_record(
                self.db,
                record.id,
                self.vehicle.user_id,
            )
        )
        self.db.refresh(expense)
        self.assertIsNone(expense.service_record_id)
        self.assertEqual(self.db.query(Expense).count(), 1)


if __name__ == "__main__":
    unittest.main()
