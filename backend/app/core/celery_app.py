from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "vehicle_maintenance",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.reminder_tasks"],
)

celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-maintenance-reminders-daily": {
            "task": "app.tasks.reminder_tasks.check_maintenance_reminders",
            "schedule": crontab(hour=8, minute=0),
        }
    },
)
