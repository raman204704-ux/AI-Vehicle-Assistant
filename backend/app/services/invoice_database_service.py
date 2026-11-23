import math
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.expense import Expense
from app.schemas.invoice import InvoiceExtraction
from app.schemas.service_history import ServiceRecordCreate
from app.services.service_history_service import (
    ServiceRecordResult,
    create_invoice_service_record,
)


class InvoiceDatabaseIntegrationError(ValueError):
    """Raised when extracted invoice values cannot be stored safely."""


def _as_finite_float(value: Decimal) -> float:
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise InvoiceDatabaseIntegrationError(
            "Numeric value is outside the supported range"
        ) from error

    if not math.isfinite(number):
        raise InvoiceDatabaseIntegrationError(
            "Numeric value is outside the supported range"
        )
    return number


def save_invoice_to_database(
    db: Session,
    document: Document,
    invoice: InvoiceExtraction,
) -> ServiceRecordResult | None:
    if (
        invoice.service_date is None
        or invoice.odometer_reading is None
        or not invoice.service_type
        or invoice.total_amount is None
    ):
        return None

    total_cost = _as_finite_float(invoice.total_amount)
    odometer_reading = _as_finite_float(
        Decimal(invoice.odometer_reading)
    )
    data = ServiceRecordCreate(
        service_date=invoice.service_date,
        odometer_reading=odometer_reading,
        service_type=invoice.service_type,
        description=invoice.service_type,
        workshop_name=invoice.workshop_name,
        total_cost=total_cost,
    )
    result = create_invoice_service_record(db, document, data)
    if result["duplicate"]:
        return result

    for item in invoice.line_items:
        if item.amount is None:
            continue
        category = (
            item.category.strip()
            if item.category and item.category.strip()
            else "other"
        )
        amount = _as_finite_float(item.amount)
        db.add(
            Expense(
                vehicle_id=document.vehicle_id,
                service_record_id=result["record"].id,
                category=category,
                amount=amount,
                expense_date=invoice.service_date,
                description=item.description,
            )
        )

    return result
