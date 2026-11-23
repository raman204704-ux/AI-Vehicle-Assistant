import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks

from app.schemas.invoice import InvoiceExtraction
from app.routers.document import upload_vehicle_document
from app.services import (
    invoice_ai_extractor,
    invoice_ocr_service,
    invoice_processing_service,
)


class InvoiceProcessingTests(unittest.TestCase):
    def test_only_explicit_invoice_types_are_processed(self):
        self.assertTrue(invoice_processing_service.should_process_invoice("Invoice"))
        self.assertTrue(
            invoice_processing_service.should_process_invoice("repair-receipt")
        )
        self.assertFalse(invoice_processing_service.should_process_invoice(None))
        self.assertFalse(invoice_processing_service.should_process_invoice(""))
        self.assertFalse(
            invoice_processing_service.should_process_invoice("insurance")
        )

    def test_ocr_parser_reads_paddle_result_json(self):
        result_json = json.dumps(
            {
                "res": {
                    "rec_texts": [" Oil change ", "  "],
                    "rec_scores": [0.92, 0.81],
                }
            }
        )

        class FakeResult:
            def __init__(self):
                self.json = result_json

        class FakeEngine:
            def predict(self, image_path):
                self.image_path = image_path
                return [FakeResult()]

        with patch.object(
            invoice_ocr_service,
            "get_ocr_engine",
            return_value=FakeEngine(),
        ):
            result = invoice_ocr_service._run_ocr(Path("invoice.png"))

        self.assertEqual(result["text"], "Oil change")
        self.assertEqual(result["confidence_scores"], [0.92])

    def test_private_file_path_must_be_inside_upload_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "documents"
            root.mkdir()
            stored_path = root / "invoice.pdf"
            stored_path.write_bytes(b"synthetic")
            outside_path = Path(directory) / "outside.pdf"
            outside_path.write_bytes(b"synthetic")

            with patch.object(invoice_processing_service, "UPLOAD_DIR", root):
                self.assertEqual(
                    invoice_processing_service.verify_private_file_path(
                        str(stored_path)
                    ),
                    stored_path.resolve(),
                )
                with self.assertRaises(
                    invoice_processing_service.InvoiceProcessingError
                ):
                    invoice_processing_service.verify_private_file_path(
                        str(outside_path)
                    )

    def test_missing_groq_key_fails_without_sending_a_request(self):
        with patch.object(invoice_ai_extractor.settings, "groq_api_key", None):
            with self.assertRaisesRegex(
                invoice_ai_extractor.InvoiceAIExtractionError,
                "GROQ_API_KEY is not configured",
            ):
                invoice_ai_extractor.extract_invoice_fields(
                    "Synthetic invoice text"
                )

    def test_invoice_file_result_is_schema_validated_and_serializable(self):
        extracted_text = {
            "text": "Test Garage\nOil change\nTotal 118.00",
            "methods": ["paddleocr"],
            "confidence_scores": [0.96],
        }
        ai_result = {
            "workshop_name": "Test Garage",
            "service_date": "2025-01-15",
            "odometer_reading": 1000,
            "service_type": "Oil change",
            "line_items": [
                {"description": "Oil change", "amount": "100.00"}
            ],
            "subtotal": "100.00",
            "tax": "18.00",
            "total_amount": "118.00",
        }

        with (
            patch.object(
                invoice_processing_service,
                "extract_document_text",
                return_value=extracted_text,
            ),
            patch.object(
                invoice_processing_service,
                "extract_invoice_fields",
                return_value=ai_result,
            ),
        ):
            result = invoice_processing_service.process_invoice_file(
                "unused.pdf",
                "application/pdf",
            )

        self.assertEqual(result["invoice"]["total_amount"], "118.00")
        self.assertFalse(result["validation"]["requires_manual_review"])
        self.assertTrue(result["extraction"]["ocr_used"])
        InvoiceExtraction.model_validate(result["invoice"])

    def test_background_processor_persists_success_and_failure_states(self):
        document = SimpleNamespace(
            id=5,
            document_type="invoice",
            processing_status="uploaded",
            file_path="private-invoice.pdf",
            file_type="application/pdf",
            extracted_data=None,
        )

        class FakeQuery:
            def filter(self, *args, **kwargs):
                self.filter_args = (args, kwargs)
                return self

            def first(self):
                return document

        class FakeSession:
            def query(self, model):
                query = FakeQuery()
                query.model = model
                return query

            def commit(self):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        success_sessions = [FakeSession(), FakeSession()]
        extraction_result = {
            "invoice": {
                "workshop_name": "Test Garage",
                "service_date": "2025-01-15",
                "odometer_reading": 1000,
                "service_type": "Oil change",
                "total_amount": "118.00",
            },
            "validation": {
                "requires_manual_review": False,
                "warnings": [],
            },
        }
        with (
            patch.object(
                invoice_processing_service,
                "SessionLocal",
                side_effect=success_sessions,
            ),
            patch.object(
                invoice_processing_service,
                "process_invoice_file",
                return_value=extraction_result,
            ),
            patch.object(
                invoice_processing_service,
                "save_invoice_to_database",
                return_value={
                    "duplicate": False,
                    "record": SimpleNamespace(id=6),
                },
            ) as save_integration,
        ):
            invoice_processing_service.process_document_in_background(5)

        self.assertEqual(document.processing_status, "processed")
        self.assertEqual(
            extraction_result["service_record"],
            {"status": "created", "id": 6},
        )
        self.assertEqual(document.extracted_data, extraction_result)
        save_integration.assert_called_once()

        document.processing_status = "uploaded"
        document.extracted_data = None
        failure_sessions = [FakeSession(), FakeSession()]
        with self.assertLogs(invoice_processing_service.logger, level="ERROR"):
            with (
                patch.object(
                    invoice_processing_service,
                    "SessionLocal",
                    side_effect=failure_sessions,
                ),
                patch.object(
                    invoice_processing_service,
                    "process_invoice_file",
                    side_effect=invoice_processing_service.InvoiceProcessingError(
                        "No readable text"
                    ),
                ),
            ):
                invoice_processing_service.process_document_in_background(5)

        self.assertEqual(document.processing_status, "failed")
        self.assertIsNone(document.extracted_data)

    def test_manual_review_persists_json_without_creating_records(self):
        document = SimpleNamespace(
            id=5,
            document_type="invoice",
            processing_status="uploaded",
            file_path="private-invoice.pdf",
            file_type="application/pdf",
            extracted_data=None,
        )

        class FakeQuery:
            def filter(self, *args, **kwargs):
                self.filter_args = (args, kwargs)
                return self

            def first(self):
                return document

        class FakeSession:
            def query(self, model):
                query = FakeQuery()
                query.model = model
                return query

            def commit(self):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        extraction_result = {
            "invoice": {
                "workshop_name": "Test Garage",
                "service_date": "2025-01-15",
                "odometer_reading": 1000,
                "service_type": "Oil change",
                "total_amount": "118.00",
            },
            "validation": {
                "requires_manual_review": True,
                "warnings": ["Low OCR confidence"],
            },
        }

        with (
            patch.object(
                invoice_processing_service,
                "SessionLocal",
                side_effect=[FakeSession(), FakeSession()],
            ),
            patch.object(
                invoice_processing_service,
                "process_invoice_file",
                return_value=extraction_result,
            ),
            patch.object(
                invoice_processing_service,
                "save_invoice_to_database",
            ) as save_records,
        ):
            invoice_processing_service.process_document_in_background(5)

        self.assertEqual(document.processing_status, "processed")
        self.assertEqual(
            extraction_result["service_record"],
            {"status": "manual_review"},
        )
        self.assertEqual(document.extracted_data, extraction_result)
        save_records.assert_not_called()

    def test_invoice_duplicate_is_flagged_for_manual_review(self):
        document = SimpleNamespace(
            id=5,
            document_type="invoice",
            processing_status="uploaded",
            file_path="private-invoice.pdf",
            file_type="application/pdf",
            extracted_data=None,
        )

        class FakeQuery:
            def filter(self, *args, **kwargs):
                self.filter_args = (args, kwargs)
                return self

            def first(self):
                return document

        class FakeSession:
            def query(self, model):
                query = FakeQuery()
                query.model = model
                return query

            def commit(self):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        extraction_result = {
            "invoice": {
                "service_date": "2026-11-15",
                "odometer_reading": 12000,
                "service_type": "Oil change",
                "total_amount": "100.00",
            },
            "validation": {
                "requires_manual_review": False,
                "warnings": [],
            },
        }

        with (
            patch.object(
                invoice_processing_service,
                "SessionLocal",
                side_effect=[FakeSession(), FakeSession()],
            ),
            patch.object(
                invoice_processing_service,
                "process_invoice_file",
                return_value=extraction_result,
            ),
            patch.object(
                invoice_processing_service,
                "save_invoice_to_database",
                return_value={
                    "duplicate": True,
                    "record": SimpleNamespace(id=18),
                },
            ),
        ):
            invoice_processing_service.process_document_in_background(5)

        self.assertEqual(document.processing_status, "processed")
        self.assertTrue(
            extraction_result["validation"]["requires_manual_review"]
        )
        self.assertIn(
            "Possible duplicate service record; manual review required",
            extraction_result["validation"]["warnings"],
        )
        self.assertEqual(
            extraction_result["service_record"],
            {
                "status": "possible_duplicate",
                "existing_record_id": 18,
            },
        )

    def test_upload_schedules_only_explicit_invoice_processing(self):
        vehicle = SimpleNamespace(id=1, user_id=7)
        current_user = SimpleNamespace(id=7)

        class FakeQuery:
            def filter(self, *args, **kwargs):
                self.filter_args = (args, kwargs)
                return self

            def first(self):
                return vehicle

        class FakeDB:
            def query(self, model):
                query = FakeQuery()
                query.model = model
                return query

        for document_type, expected_task_count in (
            ("invoice", 1),
            ("insurance", 0),
            (None, 0),
        ):
            with self.subTest(document_type=document_type):
                background_tasks = BackgroundTasks()
                document = SimpleNamespace(
                    id=5,
                    document_type=document_type,
                )
                with patch(
                    "app.routers.document.upload_document",
                    return_value=document,
                ):
                    upload_vehicle_document(
                        vehicle_id=1,
                        background_tasks=background_tasks,
                        file=object(),
                        document_type=document_type,
                        db=FakeDB(),
                        current_user=current_user,
                    )

                self.assertEqual(
                    len(background_tasks.tasks),
                    expected_task_count,
                )
                if expected_task_count:
                    self.assertIs(
                        background_tasks.tasks[0].func,
                        invoice_processing_service.process_document_in_background,
                    )


if __name__ == "__main__":
    unittest.main()
