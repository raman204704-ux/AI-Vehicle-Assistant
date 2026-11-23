from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VehicleCreate(BaseModel):
    vehicle_name: str
    manufacturer: str
    model: str
    year: int = Field(ge=1900, le=2100)
    fuel_type: str
    registration_number: str
    current_odometer: float = Field(ge=0)


class VehicleResponse(BaseModel):
    id: int
    vehicle_name: str
    manufacturer: str
    model: str
    year: int
    fuel_type: str
    registration_number: str
    current_odometer: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VehicleUpdate(BaseModel):
    vehicle_name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    fuel_type: str | None = None
    registration_number: str | None = None
    current_odometer: float | None = Field(default=None, ge=0)
