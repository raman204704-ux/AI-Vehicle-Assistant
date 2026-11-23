import unittest
from datetime import date, datetime, timezone

from pydantic import ValidationError

from app.schemas.service_history import (
    ServiceRecordCreate,
    ServiceRecordResponse,
    ServiceRecordUpdate,
)


class ServiceHistorySchemaTests(unittest.TestCase):
    def test_create_rejects_client_supplied_provenance(self):
        with self.assertRaises(ValidationError):
            ServiceRecordCreate(
                service_date=date(2026, 11, 20),
                odometer_reading=12000,
                service_type="Oil change",
                source_type="invoice",
            )

        with self.assertRaises(ValidationError):
            ServiceRecordUpdate(source_document_id=10)

    def test_create_requires_positive_odometer_reading(self):
        with self.assertRaises(ValidationError):
            ServiceRecordCreate(
                service_date=date(2026, 11, 20),
                odometer_reading=0,
                service_type="Oil change",
            )

    def test_response_can_be_created_from_model_attributes(self):
        record = type(
            "Record",
            (),
            {
                "id": 1,
                "vehicle_id": 2,
                "source_document_id": None,
                "service_date": date(2026, 11, 20),
                "odometer_reading": 12000.0,
                "service_type": "Oil change",
                "description": None,
                "workshop_name": None,
                "total_cost": 0.0,
                "source_type": "manual",
                "created_at": datetime.now(timezone.utc),
            },
        )()

        response = ServiceRecordResponse.model_validate(record)

        self.assertEqual(response.source_type, "manual")
        self.assertIsNone(response.source_document_id)


if __name__ == "__main__":
    unittest.main()
