import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.document import Document
from app.schemas.invoice import InvoiceExtraction
from app.services.document_service import UPLOAD_DIR
from app.services.invoice_database_service import save_invoice_to_database
from app.services.invoice_ai_extractor import (
    InvoiceAIExtractionError,
    extract_invoice_fields,
)
from app.services.invoice_ocr_service import (
    InvoiceOCRError,
    extract_image_ocr,
    extract_pdf_page_ocr,
)
from app.services.invoice_text_extractor import (
    InvoiceExtractionError,
    extract_pdf_text,
)
from app.services.invoice_validation_service import (
    validate_invoice_business_rules,
)

logger = logging.getLogger(__name__)

MAX_LLM_TEXT_CHARACTERS = 40_000
INVOICE_DOCUMENT_TYPES = {
    "bill",
    "bills",
    "invoice",
    "invoices",
    "receipt",
    "receipts",
}


class DocumentTextExtraction(TypedDict):
    text: str
    methods: list[str]
    confidence_scores: list[float]


class InvoiceProcessingError(ValueError):
    """Raised when a stored document cannot be processed as an invoice."""


def _flag_invoice_for_review(
    validation: dict[str, object],
    warning: str,
) -> None:
    warnings = validation.get("warnings")
    if not isinstance(warnings, list) or not all(
        isinstance(item, str) for item in warnings
    ):
        raise InvoiceProcessingError("Invoice warnings are invalid")

    validation["requires_manual_review"] = True
    if warning not in warnings:
        warnings.append(warning)


def should_process_invoice(document_type: str | None) -> bool:
    if not document_type or not document_type.strip():
        return False

    words = set(re.findall(r"[a-z]+", document_type.casefold()))
    return bool(words & INVOICE_DOCUMENT_TYPES)


def verify_private_file_path(file_path: str) -> Path:
    try:
        storage_directory = UPLOAD_DIR.resolve(strict=True)
        path = Path(file_path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise InvoiceProcessingError(
            "Document file does not exist"
        ) from error

    if path.parent != storage_directory:
        raise InvoiceProcessingError("Invalid document storage path")
    if not path.is_file():
        raise InvoiceProcessingError("Document file not found")
    return path


def extract_document_text(
    file_path: str,
    file_type: str,
) -> DocumentTextExtraction:
    path = verify_private_file_path(file_path)
    confidence_scores: list[float] = []
    extraction_methods: set[str] = set()
    extracted_pages: list[str] = []

    if file_type == "application/pdf":
        pdf_result = extract_pdf_text(path)
        for page_data in pdf_result["pages"]:
            page_number = page_data["page_number"]
            if page_data["requires_ocr"]:
                ocr_result = extract_pdf_page_ocr(path, page_number)
                ocr_text = ocr_result["text"]
                confidence_scores.extend(ocr_result["confidence_scores"])
                extraction_methods.add("paddleocr")
                page_text = ocr_text if ocr_text.strip() else page_data["text"]
                if not ocr_text.strip() and page_data["text"].strip():
                    extraction_methods.add("pymupdf")
            else:
                page_text = page_data["text"]
                extraction_methods.add("pymupdf")

            if page_text.strip():
                extracted_pages.append(f"Page {page_number}:\n{page_text}")

        full_text = "\n\n".join(extracted_pages)
    elif file_type in {"image/jpeg", "image/png"}:
        expected_suffixes = {
            "image/jpeg": {".jpg", ".jpeg"},
            "image/png": {".png"},
        }
        if path.suffix.lower() not in expected_suffixes[file_type]:
            raise InvoiceProcessingError(
                "Image extension does not match document type"
            )
        ocr_result = extract_image_ocr(path)
        full_text = ocr_result["text"]
        confidence_scores.extend(ocr_result["confidence_scores"])
        extraction_methods.add("paddleocr")
    else:
        raise InvoiceProcessingError("Unsupported document type")

    if not full_text.strip():
        raise InvoiceProcessingError("No readable text found in invoice")
    if len(full_text) > MAX_LLM_TEXT_CHARACTERS:
        raise InvoiceProcessingError(
            "Invoice text exceeds the AI processing limit"
        )

    return {
        "text": full_text,
        "methods": sorted(extraction_methods),
        "confidence_scores": confidence_scores,
    }


def process_invoice_file(
    file_path: str,
    file_type: str,
) -> dict[str, object]:
    extraction = extract_document_text(file_path, file_type)
    ai_response = extract_invoice_fields(str(extraction["text"]))
    invoice = InvoiceExtraction.model_validate(ai_response)
    validation = validate_invoice_business_rules(
        invoice,
        extraction["confidence_scores"],
    )

    methods = extraction["methods"]
    return {
        "schema_version": 1,
        "invoice": invoice.model_dump(mode="json"),
        "validation": validation,
        "extraction": {
            "methods": methods,
            "ocr_used": "paddleocr" in methods,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def process_document_in_background(document_id: int) -> None:
    db: Session = SessionLocal()
    try:
        document = (
            db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )
        if document is None:
            return
        if not should_process_invoice(document.document_type):
            return
        if document.processing_status in {"processing", "processed"}:
            return

        file_path = document.file_path
        file_type = document.file_type
        document.processing_status = "processing"
        document.extracted_data = None
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Could not start invoice processing for document %s",
            document_id,
        )
        return
    finally:
        db.close()

    try:
        extraction_result = process_invoice_file(file_path, file_type)
        final_status = "processed"
    except (
        InvoiceProcessingError,
        InvoiceExtractionError,
        InvoiceOCRError,
        InvoiceAIExtractionError,
        ValueError,
        OSError,
        RuntimeError,
    ):
        logger.exception(
            "Invoice processing failed for document %s",
            document_id,
        )
        extraction_result = None
        final_status = "failed"
    except Exception:
        logger.exception(
            "Unexpected invoice processing failure for document %s",
            document_id,
        )
        extraction_result = None
        final_status = "failed"

    db = SessionLocal()
    try:
        document = (
            db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )
        if document is None:
            return

        if extraction_result is not None:
            invoice_payload = extraction_result.get("invoice")
            validation = extraction_result.get("validation")
            if not isinstance(invoice_payload, dict) or not isinstance(
                validation, dict
            ):
                raise InvoiceProcessingError(
                    "Invoice processing result is incomplete"
                )

            requires_manual_review = validation.get(
                "requires_manual_review"
            )
            if not isinstance(requires_manual_review, bool):
                raise InvoiceProcessingError(
                    "Invoice validation result is invalid"
                )

            if requires_manual_review:
                extraction_result["service_record"] = {
                    "status": "manual_review"
                }
            else:
                invoice = InvoiceExtraction.model_validate(invoice_payload)
                integration_result = save_invoice_to_database(
                    db,
                    document,
                    invoice,
                )
                if integration_result is None:
                    _flag_invoice_for_review(
                        validation,
                        "Required service data is missing",
                    )
                    extraction_result["service_record"] = {
                        "status": "manual_review"
                    }
                elif integration_result["duplicate"]:
                    _flag_invoice_for_review(
                        validation,
                        "Possible duplicate service record; manual review required",
                    )
                    extraction_result["service_record"] = {
                        "status": "possible_duplicate",
                        "existing_record_id": integration_result["record"].id,
                    }
                else:
                    extraction_result["service_record"] = {
                        "status": "created",
                        "id": integration_result["record"].id,
                    }

            document.extracted_data = extraction_result

        document.processing_status = final_status
        db.commit()
    except (SQLAlchemyError, ValueError, TypeError):
        db.rollback()
        logger.exception(
            "Could not save invoice processing result for document %s",
            document_id,
        )
        try:
            document = (
                db.query(Document)
                .filter(Document.id == document_id)
                .first()
            )
            if document is not None:
                document.processing_status = "failed"
                if extraction_result is not None:
                    document.extracted_data = extraction_result
                db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "Could not mark invoice document %s as failed",
                document_id,
            )
    finally:
        db.close()
