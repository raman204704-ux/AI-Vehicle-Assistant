import calendar
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.maintenance_reminder import MaintenanceReminder
from app.models.service_record import ServiceRecord
from app.models.vehicle import Vehicle
from app.schemas.reminder import ReminderCreate, ReminderUpdate

LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


class ReminderNotFoundError(Exception):
    """Raised when a reminder or vehicle is outside the user's scope."""


class ReminderInputError(Exception):
    """Raised when a reminder's state would violate its business rules."""


class ReminderStateError(Exception):
    """Raised when the requested reminder transition is not allowed."""


def add_months(original_date: date, months: int) -> date:
    month_index = original_date.month - 1 + months
    year = original_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(original_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


class ReminderService:
    def __init__(self, db: Session):
        self.db = db

    def get_vehicle(self, vehicle_id: int, user_id: int) -> Vehicle:
        vehicle = (
            self.db.query(Vehicle)
            .filter(
                Vehicle.id == vehicle_id,
                Vehicle.user_id == user_id,
            )
            .first()
        )
        if vehicle is None:
            raise ReminderNotFoundError("Vehicle not found")
        return vehicle

    def get_reminder(
        self,
        reminder_id: int,
        user_id: int,
        lock: bool = False,
    ) -> MaintenanceReminder:
        query = self.db.query(MaintenanceReminder).filter(
            MaintenanceReminder.id == reminder_id,
            MaintenanceReminder.user_id == user_id,
        )
        if lock:
            query = query.with_for_update()
        reminder = query.first()
        if reminder is None:
            raise ReminderNotFoundError("Reminder not found")
        return reminder

    def create_reminder(
        self,
        vehicle_id: int,
        user_id: int,
        data: ReminderCreate,
    ) -> MaintenanceReminder:
        self.get_vehicle(vehicle_id, user_id)
        reminder = MaintenanceReminder(
            user_id=user_id,
            vehicle_id=vehicle_id,
            **data.model_dump(),
        )
        self.db.add(reminder)
        _commit(self.db)
        self.db.refresh(reminder)
        return reminder

    def get_reminders(
        self,
        vehicle_id: int,
        user_id: int,
    ) -> list[MaintenanceReminder]:
        self.get_vehicle(vehicle_id, user_id)
        return (
            self.db.query(MaintenanceReminder)
            .filter(
                MaintenanceReminder.vehicle_id == vehicle_id,
                MaintenanceReminder.user_id == user_id,
            )
            .order_by(
                MaintenanceReminder.due_date.asc(),
                MaintenanceReminder.due_odometer.asc(),
                MaintenanceReminder.id.asc(),
            )
            .all()
        )

    def update_reminder(
        self,
        reminder_id: int,
        user_id: int,
        data: ReminderUpdate,
    ) -> MaintenanceReminder:
        reminder = self.get_reminder(reminder_id, user_id, lock=True)
        changes = data.model_dump(exclude_unset=True)

        if "title" in changes and changes["title"] is None:
            raise ReminderInputError("Title cannot be null")

        next_due_date = changes.get("due_date", reminder.due_date)
        next_due_odometer = changes.get("due_odometer", reminder.due_odometer)
        if (
            reminder.status == "active"
            and next_due_date is None
            and next_due_odometer is None
        ):
            raise ReminderInputError(
                "A reminder must retain a due date or due odometer"
            )

        for field, value in changes.items():
            setattr(reminder, field, value)
        _commit(self.db)
        self.db.refresh(reminder)
        return reminder

    def complete_reminder(
        self,
        reminder_id: int,
        user_id: int,
        today: date | None = None,
        completed_at: datetime | None = None,
    ) -> MaintenanceReminder:
        reminder = self.get_reminder(reminder_id, user_id, lock=True)
        if reminder.status != "active":
            raise ReminderStateError("Only active reminders can be completed")

        vehicle = self.get_vehicle(reminder.vehicle_id, user_id)
        latest_service = (
            self.db.query(ServiceRecord)
            .filter(ServiceRecord.vehicle_id == reminder.vehicle_id)
            .order_by(
                ServiceRecord.service_date.desc(),
                ServiceRecord.id.desc(),
            )
            .first()
        )
        latest_odometer = (
            latest_service.odometer_reading if latest_service else None
        )
        if vehicle.current_odometer is not None:
            latest_odometer = (
                vehicle.current_odometer
                if latest_odometer is None
                else max(latest_odometer, vehicle.current_odometer)
            )

        completion_date = today or datetime.now(LOCAL_TIMEZONE).date()
        next_due_date = (
            add_months(
                reminder.due_date or completion_date,
                reminder.repeat_interval_months,
            )
            if reminder.repeat_interval_months is not None
            else None
        )
        if (
            reminder.repeat_interval_km is not None
            and latest_odometer is None
        ):
            raise ReminderInputError(
                "Cannot calculate the next mileage reminder without an "
                "odometer reading"
            )
        next_due_odometer = (
            latest_odometer + reminder.repeat_interval_km
            if reminder.repeat_interval_km is not None
            and latest_odometer is not None
            else None
        )

        reminder.due_date = next_due_date
        reminder.due_odometer = next_due_odometer
        reminder.completed_at = completed_at or datetime.now(timezone.utc)
        reminder.status = (
            "active"
            if next_due_date is not None or next_due_odometer is not None
            else "completed"
        )
        _commit(self.db)
        self.db.refresh(reminder)
        return reminder

    def cancel_reminder(
        self,
        reminder_id: int,
        user_id: int,
    ) -> MaintenanceReminder:
        reminder = self.get_reminder(reminder_id, user_id, lock=True)
        if reminder.status != "active":
            raise ReminderStateError("Only active reminders can be cancelled")
        reminder.status = "cancelled"
        reminder.is_enabled = False
        _commit(self.db)
        self.db.refresh(reminder)
        return reminder
