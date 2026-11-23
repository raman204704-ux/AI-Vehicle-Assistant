import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError

from app.core.celery_app import celery_app
from app.database.connection import SessionLocal
from app.models.maintenance_reminder import MaintenanceReminder
from app.models.vehicle import Vehicle
from app.services.notification_service import (
    create_notification,
    evaluate_reminder,
)

logger = logging.getLogger(__name__)
LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


def reminder_check_date() -> date:
    return datetime.now(LOCAL_TIMEZONE).date()


@celery_app.task(
    name="app.tasks.reminder_tasks.check_maintenance_reminders",
    autoretry_for=(SQLAlchemyError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def check_maintenance_reminders() -> dict[str, int]:
    db = SessionLocal()
    try:
        reminders = (
            db.query(MaintenanceReminder, Vehicle)
            .join(
                Vehicle,
                and_(
                    Vehicle.id == MaintenanceReminder.vehicle_id,
                    Vehicle.user_id == MaintenanceReminder.user_id,
                ),
            )
            .filter(
                MaintenanceReminder.status == "active",
                MaintenanceReminder.is_enabled.is_(True),
            )
            .all()
        )
        generated = 0
        today = reminder_check_date()

        for reminder, vehicle in reminders:
            notification_type, reasons = evaluate_reminder(
                reminder,
                vehicle,
                today,
            )
            if notification_type is None:
                continue
            notification = create_notification(
                db,
                reminder,
                notification_type,
                reasons,
            )
            if notification is not None:
                generated += 1

        logger.info(
            "Checked %d maintenance reminders; created %d notifications",
            len(reminders),
            generated,
        )
        return {
            "checked": len(reminders),
            "notifications_created": generated,
        }
    finally:
        db.close()
