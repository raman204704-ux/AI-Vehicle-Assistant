from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLineItem(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )

    description: str = Field(min_length=1, max_length=250)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    amount: Decimal | None = Field(default=None, ge=0)
    category: str | None = Field(default=None, max_length=80)


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )

    workshop_name: str | None = Field(default=None, max_length=150)
    invoice_number: str | None = Field(default=None, max_length=100)
    invoice_date: date | None = None
    service_date: date | None = None
    odometer_reading: int | None = Field(default=None, ge=0)
    vehicle_registration_number: str | None = Field(default=None, max_length=30)
    service_type: str | None = Field(default=None, max_length=100)
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    subtotal: Decimal | None = Field(default=None, ge=0)
    tax: Decimal | None = Field(default=None, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)
