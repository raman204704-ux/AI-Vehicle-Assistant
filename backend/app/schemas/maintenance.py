from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MaintenanceRuleResponse(BaseModel):
    id: int
    maintenance_type: str
    service_type: str
    manufacturer: str | None
    model: str | None
    fuel_type: str | None
    interval_km: int | None
    interval_months: int | None
    source_title: str
    source_url: str
    effective_date: date | None
    verified_at: date

    model_config = ConfigDict(from_attributes=True)


class MaintenancePrediction(BaseModel):
    rule_id: int
    maintenance_type: str
    status: Literal["overdue", "due_soon", "not_due", "unknown"]
    last_service_date: date | None
    last_service_odometer: float | None
    current_odometer: float
    next_due_odometer: float | None
    remaining_km: float | None
    next_due_date: date | None
    remaining_days: int | None
    source_title: str
    source_url: str


class MaintenancePredictionResponse(BaseModel):
    vehicle_id: int
    vehicle_name: str
    current_odometer: float
    predictions: list[MaintenancePrediction]
    generated_at: datetime
