from pathlib import Path
from typing import Literal, TypedDict

import pymupdf

from app.services.document_service import UPLOAD_DIR

MAX_PDF_PAGES = 50
MAX_EXTRACTED_CHARACTERS = 120_000
MIN_TEXT_CHARACTERS_PER_PAGE = 25


class InvoiceExtractionError(Exception):
    """Raised when an invoice PDF cannot be processed."""


class ExtractedPage(TypedDict):
    page_number: int
    text: str
    requires_ocr: bool


class PDFTextExtractionResult(TypedDict):
    file_name: str
    total_pages: int
    extraction_status: Literal[
        "text_extracted",
        "ocr_required",
        "partial_ocr_required",
    ]
    full_text: str
    pages: list[ExtractedPage]
    ocr_required_pages: list[int]


def extract_pdf_text(file_path: str | Path) -> PDFTextExtractionResult:
    try:
        path = Path(file_path).resolve(strict=True)
        storage_directory = UPLOAD_DIR.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise InvoiceExtractionError("Invoice file does not exist") from error

    if path.parent != storage_directory or not path.is_file():
        raise InvoiceExtractionError("Invalid invoice file")

    if path.suffix.lower() != ".pdf":
        raise InvoiceExtractionError("Only PDF invoices are supported")

    try:
        with pymupdf.open(path) as pdf:
            if not pdf.is_pdf:
                raise InvoiceExtractionError("File is not a PDF")

            if pdf.needs_pass:
                raise InvoiceExtractionError(
                    "Password-protected PDFs are not supported"
                )

            if pdf.page_count == 0:
                raise InvoiceExtractionError("PDF contains no pages")

            if pdf.page_count > MAX_PDF_PAGES:
                raise InvoiceExtractionError(
                    f"PDF exceeds the {MAX_PDF_PAGES}-page limit"
                )

            extracted_pages: list[ExtractedPage] = []
            ocr_required_pages: list[int] = []
            text_parts: list[str] = []
            extracted_character_count = 0

            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text", sort=True).strip()
                alphanumeric_count = sum(
                    character.isalnum() for character in text
                )
                requires_ocr = (
                    alphanumeric_count < MIN_TEXT_CHARACTERS_PER_PAGE
                )
                if requires_ocr:
                    ocr_required_pages.append(page_number)

                extracted_pages.append(
                    {
                        "page_number": page_number,
                        "text": text,
                        "requires_ocr": requires_ocr,
                    }
                )

                if text:
                    text_part = f"Page {page_number}:\n{text}"
                    additional_characters = len(text_part)
                    if text_parts:
                        additional_characters += 2
                    if (
                        extracted_character_count + additional_characters
                        > MAX_EXTRACTED_CHARACTERS
                    ):
                        raise InvoiceExtractionError(
                            "Extracted PDF text exceeds the processing limit"
                        )
                    text_parts.append(text_part)
                    extracted_character_count += additional_characters

            if not ocr_required_pages:
                extraction_status: Literal[
                    "text_extracted",
                    "ocr_required",
                    "partial_ocr_required",
                ] = "text_extracted"
            elif len(ocr_required_pages) == pdf.page_count:
                extraction_status = "ocr_required"
            else:
                extraction_status = "partial_ocr_required"

            return {
                "file_name": path.name,
                "total_pages": pdf.page_count,
                "extraction_status": extraction_status,
                "full_text": "\n\n".join(text_parts),
                "pages": extracted_pages,
                "ocr_required_pages": ocr_required_pages,
            }
    except InvoiceExtractionError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise InvoiceExtractionError(
            "Unable to read the PDF invoice"
        ) from error
