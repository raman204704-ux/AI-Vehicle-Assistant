from datetime import date
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.maintenance_reminder import MaintenanceReminder
from app.models.notification import Notification
from app.models.vehicle import Vehicle

NotificationType = Literal["upcoming", "overdue"]


def evaluate_reminder(
    reminder: MaintenanceReminder,
    vehicle: Vehicle,
    today: date,
) -> tuple[NotificationType | None, list[str]]:
    is_overdue = False
    is_upcoming = False
    reasons: list[str] = []

    if reminder.due_date is not None:
        days_remaining = (reminder.due_date - today).days
        if days_remaining < 0:
            is_overdue = True
            reasons.append(f"Overdue by {abs(days_remaining)} days")
        elif days_remaining <= reminder.reminder_days_before:
            is_upcoming = True
            reasons.append(f"Due in {days_remaining} days")

    if reminder.due_odometer is not None:
        remaining_km = reminder.due_odometer - vehicle.current_odometer
        if remaining_km < 0:
            is_overdue = True
            reasons.append(f"Overdue by {abs(remaining_km):g} km")
        elif remaining_km <= settings.reminder_mileage_threshold_km:
            is_upcoming = True
            reasons.append(f"Due in {remaining_km:g} km")

    if is_overdue:
        return "overdue", reasons
    if is_upcoming:
        return "upcoming", reasons
    return None, reasons


def create_notification(
    db: Session,
    reminder: MaintenanceReminder,
    notification_type: NotificationType,
    reasons: list[str],
) -> Notification | None:
    idempotency_key = (
        f"{reminder.id}:{notification_type}:"
        f"{reminder.due_date}:{reminder.due_odometer}"
    )
    notification = Notification(
        user_id=reminder.user_id,
        vehicle_id=reminder.vehicle_id,
        reminder_id=reminder.id,
        title=reminder.title,
        message=f"{reminder.title}: {', '.join(reasons)}",
        notification_type=notification_type,
        idempotency_key=idempotency_key,
    )
    db.add(notification)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(Notification)
            .filter(
                Notification.user_id == reminder.user_id,
                Notification.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is not None:
            return None
        raise
    db.refresh(notification)
    return notification
