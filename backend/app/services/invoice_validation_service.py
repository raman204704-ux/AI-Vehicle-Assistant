import math
from datetime import date
from decimal import Decimal

from app.schemas.invoice import InvoiceExtraction


def validate_invoice_business_rules(
    invoice: InvoiceExtraction,
    ocr_confidence_scores: list[float],
) -> dict[str, object]:
    warnings: list[str] = []

    if invoice.service_date is None:
        warnings.append("Service date could not be identified")
    if invoice.odometer_reading is None or invoice.odometer_reading <= 0:
        warnings.append("A valid odometer reading could not be identified")
    if not invoice.service_type or len(invoice.service_type.strip()) < 2:
        warnings.append("Service type could not be identified")
    if invoice.total_amount is None:
        warnings.append("Total invoice amount is missing")
    if invoice.workshop_name is None:
        warnings.append("Workshop name could not be identified")
    if invoice.service_date is not None and invoice.service_date > date.today():
        warnings.append("Service date is in the future")

    if (
        invoice.subtotal is not None
        and invoice.tax is not None
        and invoice.total_amount is not None
    ):
        calculated_total = invoice.subtotal + invoice.tax
        if abs(calculated_total - invoice.total_amount) > Decimal("1.00"):
            warnings.append("Subtotal and tax do not match total amount")

    line_item_amounts = [
        item.amount for item in invoice.line_items if item.amount is not None
    ]
    if line_item_amounts and invoice.subtotal is not None:
        calculated_subtotal = sum(line_item_amounts, Decimal("0"))
        if abs(calculated_subtotal - invoice.subtotal) > Decimal("2.00"):
            warnings.append("Line item total does not match subtotal")

    valid_scores = [
        float(score)
        for score in ocr_confidence_scores
        if math.isfinite(float(score)) and 0 <= float(score) <= 1
    ]
    average_confidence = (
        sum(valid_scores) / len(valid_scores) if valid_scores else None
    )
    if average_confidence is not None and average_confidence < 0.75:
        warnings.append(
            "OCR confidence is low; manual review recommended"
        )

    return {
        "requires_manual_review": bool(warnings),
        "warnings": warnings,
        "ocr_average_confidence": average_confidence,
    }
