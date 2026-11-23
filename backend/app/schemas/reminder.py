from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ReminderCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    category: str = Field(min_length=2, max_length=100)
    due_date: date | None = None
    due_odometer: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    repeat_interval_months: int | None = Field(default=None, ge=1)
    repeat_interval_km: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    reminder_days_before: int = Field(default=7, ge=0, le=365)

    @field_validator("title", "category")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_due_information(self) -> "ReminderCreate":
        if self.due_date is None and self.due_odometer is None:
            raise ValueError("Provide at least a due date or due odometer")
        return self


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    due_date: date | None = None
    due_odometer: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    reminder_days_before: int | None = Field(default=None, ge=0, le=365)
    is_enabled: bool | None = None

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ReminderResponse(BaseModel):
    id: int
    vehicle_id: int
    title: str
    description: str | None
    category: str
    due_date: date | None
    due_odometer: float | None
    repeat_interval_months: int | None
    repeat_interval_km: float | None
    reminder_days_before: int
    status: str
    is_enabled: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationResponse(BaseModel):
    id: int
    vehicle_id: int
    reminder_id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
