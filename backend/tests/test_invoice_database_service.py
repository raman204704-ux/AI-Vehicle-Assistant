import unittest
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.models import Document, Expense, ServiceRecord, Vehicle
from app.schemas.invoice import InvoiceExtraction
from app.services.invoice_database_service import save_invoice_to_database


class InvoiceDatabaseServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        vehicle = Vehicle(
            vehicle_name="Test Vehicle",
            manufacturer="Test",
            model="Model",
            year=2020,
            fuel_type="petrol",
            registration_number="TEST-001",
        )
        self.db.add(vehicle)
        self.db.flush()

        self.document = Document(
            vehicle_id=vehicle.id,
            file_name="invoice.pdf",
            file_path="private/invoice.pdf",
            file_type="application/pdf",
        )
        self.db.add(self.document)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_saves_one_service_and_only_priced_line_items_idempotently(self):
        invoice = InvoiceExtraction.model_validate(
            {
                "workshop_name": "Test Garage",
                "invoice_date": "2026-10-16",
                "service_date": "2026-10-15",
                "odometer_reading": 105000,
                "service_type": "Engine Oil Replacement",
                "total_amount": "3800.00",
                "line_items": [
                    {
                        "description": "Engine Oil",
                        "category": "lubricant",
                        "amount": "2500.00",
                    },
                    {
                        "description": "Oil Filter",
                        "category": "spare_parts",
                        "amount": "500.00",
                    },
                    {
                        "description": "Labour",
                        "amount": "800.00",
                    },
                    {
                        "description": "Unpriced note",
                        "amount": None,
                    },
                ],
            }
        )

        result = save_invoice_to_database(
            self.db,
            self.document,
            invoice,
        )
        self.db.commit()
        repeated_record = save_invoice_to_database(
            self.db,
            self.document,
            invoice,
        )
        self.db.commit()

        self.assertFalse(result["duplicate"])
        service_record = result["record"]
        self.assertIsNotNone(service_record)
        self.assertTrue(repeated_record["duplicate"])
        self.assertEqual(
            repeated_record["record"].id,
            result["record"].id,
        )
        records = self.db.query(ServiceRecord).all()
        expenses = (
            self.db.query(Expense)
            .order_by(Expense.id)
            .all()
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(len(expenses), 3)
        self.assertEqual(records[0].source_document_id, self.document.id)
        self.assertEqual(records[0].source_type, "invoice")
        self.assertEqual(records[0].service_date, date(2026, 10, 15))
        self.assertEqual(records[0].total_cost, 3800.0)
        self.assertEqual(
            [expense.category for expense in expenses],
            ["lubricant", "spare_parts", "other"],
        )
        self.assertTrue(
            all(
                expense.service_record_id == records[0].id
                for expense in expenses
            )
        )
        self.assertEqual(
            [expense.amount for expense in expenses],
            [2500.0, 500.0, 800.0],
        )
    def test_invoice_date_alone_does_not_create_service_record(self):
        invoice = InvoiceExtraction.model_validate(
            {
                "invoice_date": "2026-10-15",
                "odometer_reading": 105000,
                "service_type": "General Servicing",
                "total_amount": "100.00",
            }
        )

        service_record = save_invoice_to_database(
            self.db,
            self.document,
            invoice,
        )

        self.assertIsNone(service_record)
        self.assertEqual(self.db.query(ServiceRecord).count(), 0)
        self.assertEqual(self.db.query(Expense).count(), 0)

    def test_invoice_matching_existing_service_is_flagged_as_duplicate(self):
        existing_record = ServiceRecord(
            vehicle_id=self.document.vehicle_id,
            service_date=date(2026, 10, 15),
            odometer_reading=105000,
            service_type="Engine Oil Replacement",
            total_cost=3800,
            source_type="manual",
        )
        self.db.add(existing_record)
        self.db.commit()

        invoice = InvoiceExtraction.model_validate(
            {
                "service_date": "2026-10-15",
                "odometer_reading": 105000,
                "service_type": "engine oil replacement",
                "total_amount": "3800.00",
                "line_items": [
                    {"description": "Engine Oil", "amount": "2500.00"}
                ],
            }
        )

        result = save_invoice_to_database(self.db, self.document, invoice)

        self.assertTrue(result["duplicate"])
        self.assertEqual(result["record"].id, existing_record.id)
        self.assertEqual(self.db.query(ServiceRecord).count(), 1)
        self.assertEqual(self.db.query(Expense).count(), 0)

    def test_manual_service_records_default_to_manual_source(self):
        record = ServiceRecord(
            vehicle_id=self.document.vehicle_id,
            service_date=date(2026, 10, 15),
            odometer_reading=105000,
            service_type="General Servicing",
        )
        self.db.add(record)
        self.db.flush()

        self.assertEqual(record.source_type, "manual")

    def test_unrepresentable_amount_is_rejected_before_records_are_added(self):
        invoice = InvoiceExtraction.model_validate(
            {
                "service_date": "2026-10-15",
                "odometer_reading": 105000,
                "service_type": "General Servicing",
                "total_amount": Decimal("1e1000"),
            }
        )

        with self.assertRaises(ValueError):
            save_invoice_to_database(self.db, self.document, invoice)

        self.assertEqual(self.db.query(ServiceRecord).count(), 0)
        self.assertEqual(self.db.query(Expense).count(), 0)


if __name__ == "__main__":
    unittest.main()
