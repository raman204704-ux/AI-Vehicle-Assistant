import json
import math
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any, TypedDict

import pymupdf

from app.core.config import settings

OCR_LOCK = Lock()


class InvoiceOCRError(Exception):
    """Raised when OCR cannot process an invoice image or page."""


class OCRResult(TypedDict):
    text: str
    confidence_scores: list[float]


@lru_cache(maxsize=2)
def get_ocr_engine(language: str = "en") -> Any:
    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang=language,
        use_doc_orientation_classify=True,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        device="cpu",
    )


def _result_mapping(result: object) -> Mapping[str, object]:
    if isinstance(result, Mapping):
        payload = result
    else:
        payload = getattr(result, "json", None)
        if callable(payload):
            payload = payload()
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return {}

    if not isinstance(payload, Mapping):
        return {}

    nested_result = payload.get("res")
    return nested_result if isinstance(nested_result, Mapping) else payload


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return []


def _run_ocr(image_path: Path) -> OCRResult:
    try:
        engine = get_ocr_engine(settings.ocr_lang)
        with OCR_LOCK:
            results = engine.predict(str(image_path))
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise InvoiceOCRError("OCR processing failed") from error

    if isinstance(results, Mapping) or hasattr(results, "json"):
        results = [results]

    try:
        result_items = list(results) if results is not None else []
    except TypeError as error:
        raise InvoiceOCRError("OCR returned an invalid result") from error

    extracted_lines: list[str] = []
    confidence_scores: list[float] = []

    for result in result_items:
        result_data = _result_mapping(result)
        texts = _as_list(result_data.get("rec_texts"))
        scores = _as_list(result_data.get("rec_scores"))

        for index, value in enumerate(texts):
            text = str(value).strip()
            if not text:
                continue
            extracted_lines.append(text)

            if index < len(scores):
                try:
                    score = float(scores[index])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(score) and 0 <= score <= 1:
                    confidence_scores.append(score)

    return {
        "text": "\n".join(extracted_lines),
        "confidence_scores": confidence_scores,
    }


def extract_image_ocr(file_path: str | Path) -> OCRResult:
    try:
        path = Path(file_path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise InvoiceOCRError("Image file does not exist") from error

    if not path.is_file():
        raise InvoiceOCRError("Invalid image file")
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise InvoiceOCRError("Unsupported image format")

    return _run_ocr(path)


def extract_pdf_page_ocr(
    pdf_path: str | Path,
    page_number: int,
) -> OCRResult:
    try:
        path = Path(pdf_path).resolve(strict=True)
        with pymupdf.open(path) as pdf:
            if not pdf.is_pdf:
                raise InvoiceOCRError("File is not a PDF")
            if pdf.needs_pass:
                raise InvoiceOCRError(
                    "Password-protected PDFs are not supported"
                )
            if page_number < 1 or page_number > pdf.page_count:
                raise InvoiceOCRError("Invalid PDF page number")

            page = pdf.load_page(page_number - 1)
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(2, 2),
                alpha=False,
            )
            with TemporaryDirectory() as temp_directory:
                image_path = Path(temp_directory) / "invoice_page.png"
                pixmap.save(str(image_path))
                return _run_ocr(image_path)
    except InvoiceOCRError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise InvoiceOCRError("Unable to render PDF page for OCR") from error
