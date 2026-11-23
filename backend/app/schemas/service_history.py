from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ServiceRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    service_date: date
    odometer_reading: float = Field(
        gt=0,
        description="Vehicle odometer reading in kilometres",
    )
    service_type: str = Field(min_length=2, max_length=100)
    description: str | None = None
    workshop_name: str | None = Field(default=None, max_length=150)
    total_cost: float = Field(default=0, ge=0)


class ServiceRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    service_date: date | None = None
    odometer_reading: float | None = Field(default=None, gt=0)
    service_type: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )
    description: str | None = None
    workshop_name: str | None = Field(default=None, max_length=150)
    total_cost: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        for field in (
            "service_date",
            "odometer_reading",
            "service_type",
            "total_cost",
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ServiceRecordResponse(BaseModel):
    id: int
    vehicle_id: int
    source_document_id: int | None
    service_date: date
    odometer_reading: float
    service_type: str
    description: str | None
    workshop_name: str | None
    total_cost: float
    source_type: str
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
