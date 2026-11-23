import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.database.connection import Base, get_db
from app.models import (
    MaintenanceReminder,
    Notification,
    User,
    Vehicle,
)
from app.routers.reminders import router
from app.schemas.reminder import ReminderCreate, ReminderUpdate
from app.services.notification_service import (
    create_notification,
    evaluate_reminder,
)
from app.services.reminder_service import ReminderService, add_months


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        owner = User(email="owner@example.com", hashed_password="test-hash")
        other = User(email="other@example.com", hashed_password="test-hash")
        self.db.add_all([owner, other])
        self.db.flush()
        self.owner_id = owner.id

        self.vehicle = Vehicle(
            user_id=owner.id,
            vehicle_name="Owner vehicle",
            manufacturer="Example",
            model="Roadster",
            year=2020,
            fuel_type="petrol",
            registration_number="REM-OWNER-1",
            current_odometer=10400,
        )
        self.other_vehicle = Vehicle(
            user_id=other.id,
            vehicle_name="Other vehicle",
            manufacturer="Example",
            model="Roadster",
            year=2020,
            fuel_type="petrol",
            registration_number="REM-OTHER-1",
            current_odometer=2000,
        )
        self.db.add_all([self.vehicle, self.other_vehicle])
        self.db.commit()
        self.vehicle_id = self.vehicle.id
        self.other_vehicle_id = self.other_vehicle.id

        app = FastAPI()
        app.include_router(router)

        def override_get_db():
            session = Session(self.engine)
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=self.owner_id
        )
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def date_reminder_body(**overrides):
        body = {
            "title": "Engine oil change",
            "description": "Check the oil and filter",
            "category": "maintenance",
            "due_date": "2026-11-28",
            "due_odometer": None,
            "repeat_interval_months": 6,
            "repeat_interval_km": None,
            "reminder_days_before": 7,
        }
        body.update(overrides)
        return body

    def test_create_and_list_vehicle_reminders(self):
        created = self.client.post(
            f"/reminders/vehicles/{self.vehicle_id}",
            json=self.date_reminder_body(),
        )
        self.assertEqual(created.status_code, 201)
        reminder_id = created.json()["id"]
        self.assertEqual(created.json()["status"], "active")
        self.assertEqual(created.json()["title"], "Engine oil change")

        listed = self.client.get(f"/reminders/vehicles/{self.vehicle_id}")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()], [reminder_id])

    def test_due_date_or_odometer_is_required(self):
        response = self.client.post(
            f"/reminders/vehicles/{self.vehicle_id}",
            json=self.date_reminder_body(due_date=None),
        )
        self.assertEqual(response.status_code, 422)

    def test_vehicle_and_reminder_ownership_is_enforced(self):
        foreign_vehicle = self.client.post(
            f"/reminders/vehicles/{self.other_vehicle_id}",
            json=self.date_reminder_body(),
        )
        self.assertEqual(foreign_vehicle.status_code, 404)

        created = self.client.post(
            f"/reminders/vehicles/{self.vehicle_id}",
            json=self.date_reminder_body(),
        )
        reminder_id = created.json()["id"]

        db = Session(self.engine)
        try:
            foreign_user_id = (
                db.query(User)
                .filter(User.email == "other@example.com")
                .one()
                .id
            )
        finally:
            db.close()
        app = FastAPI()
        app.include_router(router)

        def override_get_db():
            session = Session(self.engine)
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=foreign_user_id
        )
        foreign_client = TestClient(app)
        try:
            response = foreign_client.patch(
                f"/reminders/{reminder_id}",
                json={"title": "Someone else's reminder"},
            )
            self.assertEqual(response.status_code, 404)
        finally:
            foreign_client.close()

    def test_update_cannot_clear_both_due_conditions(self):
        created = self.client.post(
            f"/reminders/vehicles/{self.vehicle_id}",
            json=self.date_reminder_body(),
        )
        reminder_id = created.json()["id"]
        response = self.client.patch(
            f"/reminders/{reminder_id}",
            json={"due_date": None},
        )
        self.assertEqual(response.status_code, 422)

        reminder = self.db.get(MaintenanceReminder, reminder_id)
        self.db.refresh(reminder)
        self.assertEqual(reminder.due_date, date(2026, 11, 28))

    def test_completion_advances_month_end_and_odometer_recurrence(self):
        reminder = ReminderService(self.db).create_reminder(
            self.vehicle_id,
            self.owner_id,
            ReminderCreate(
                title="Oil change",
                category="maintenance",
                due_date=date(2026, 1, 31),
                due_odometer=12000,
                repeat_interval_months=1,
                repeat_interval_km=5000,
            ),
        )

        completed = ReminderService(self.db).complete_reminder(
            reminder.id,
            self.owner_id,
            today=date(2026, 2, 1),
            completed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(completed.due_date, date(2026, 2, 28))
        self.assertEqual(completed.due_odometer, 15400)
        self.assertEqual(completed.status, "active")
        self.assertIsNotNone(completed.completed_at)

    def test_non_recurring_completion_marks_reminder_complete(self):
        reminder = ReminderService(self.db).create_reminder(
            self.vehicle_id,
            self.owner_id,
            ReminderCreate(
                title="One-time inspection",
                category="inspection",
                due_odometer=11000,
            ),
        )
        completed = ReminderService(self.db).complete_reminder(
            reminder.id,
            self.owner_id,
            today=date(2026, 11, 23),
            completed_at=datetime(2026, 11, 23, tzinfo=timezone.utc),
        )
        self.assertEqual(completed.status, "completed")
        self.assertIsNone(completed.due_date)
        self.assertIsNone(completed.due_odometer)
        updated = ReminderService(self.db).update_reminder(
            completed.id,
            self.owner_id,
            ReminderUpdate(title="Completed inspection"),
        )
        self.assertEqual(updated.title, "Completed inspection")

    def test_upcoming_and_overdue_evaluation(self):
        upcoming = MaintenanceReminder(
            user_id=self.owner_id,
            vehicle_id=self.vehicle_id,
            title="Upcoming service",
            category="maintenance",
            due_date=date(2026, 11, 26),
            reminder_days_before=7,
        )
        notification_type, reasons = evaluate_reminder(
            upcoming,
            self.vehicle,
            date(2026, 11, 23),
        )
        self.assertEqual(notification_type, "upcoming")
        self.assertIn("Due in 3 days", reasons)

        overdue = MaintenanceReminder(
            user_id=self.owner_id,
            vehicle_id=self.vehicle_id,
            title="Overdue service",
            category="maintenance",
            due_date=date(2026, 11, 22),
            due_odometer=10000,
        )
        notification_type, reasons = evaluate_reminder(
            overdue,
            self.vehicle,
            date(2026, 11, 23),
        )
        self.assertEqual(notification_type, "overdue")
        self.assertIn("Overdue by 1 days", reasons)
        self.assertIn("Overdue by 400 km", reasons)

    def test_task_generates_only_one_notification_per_due_cycle(self):
        reminder = ReminderService(self.db).create_reminder(
            self.vehicle_id,
            self.owner_id,
            ReminderCreate(
                title="Upcoming oil change",
                category="maintenance",
                due_date=date(2026, 11, 26),
            ),
        )

        from app.tasks import reminder_tasks

        with (
            patch.object(
                reminder_tasks,
                "SessionLocal",
                side_effect=lambda: Session(self.engine),
            ),
            patch.object(
                reminder_tasks,
                "reminder_check_date",
                return_value=date(2026, 11, 23),
            ),
        ):
            first = reminder_tasks.check_maintenance_reminders.run()
            second = reminder_tasks.check_maintenance_reminders.run()

        self.assertEqual(first["checked"], 1)
        self.assertEqual(first["notifications_created"], 1)
        self.assertEqual(second["notifications_created"], 0)
        self.assertEqual(
            self.db.query(Notification)
            .filter(Notification.reminder_id == reminder.id)
            .count(),
            1,
        )

    def test_notification_history_and_read_updates_are_user_scoped(self):
        reminder = ReminderService(self.db).create_reminder(
            self.vehicle_id,
            self.owner_id,
            ReminderCreate(
                title="Oil change",
                category="maintenance",
                due_date=date(2026, 11, 26),
            ),
        )
        owned = create_notification(
            self.db,
            reminder,
            "upcoming",
            ["Due in 3 days"],
        )
        unread = Notification(
            user_id=self.owner_id,
            vehicle_id=self.vehicle_id,
            reminder_id=reminder.id,
            title=reminder.title,
            message="Second due cycle",
            notification_type="overdue",
            idempotency_key="second-cycle",
        )
        other_user_id = (
            self.db.query(User)
            .filter(User.email == "other@example.com")
            .one()
            .id
        )
        foreign_reminder = MaintenanceReminder(
            user_id=other_user_id,
            vehicle_id=self.other_vehicle_id,
            title="Private reminder",
            category="maintenance",
            due_date=date(2026, 11, 26),
        )
        self.db.add(foreign_reminder)
        self.db.flush()
        foreign_notification = Notification(
            user_id=other_user_id,
            vehicle_id=self.other_vehicle_id,
            reminder_id=foreign_reminder.id,
            title="Private reminder",
            message="Private",
            notification_type="upcoming",
            idempotency_key="private-cycle",
        )
        self.db.add_all([unread, foreign_notification])
        self.db.commit()

        unread_response = self.client.get(
            "/reminders/notifications?unread_only=true"
        )
        self.assertEqual(unread_response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in unread_response.json()},
            {owned.id, unread.id},
        )
        self.assertNotIn(
            foreign_notification.id,
            {item["id"] for item in unread_response.json()},
        )

        marked = self.client.patch(
            f"/reminders/notifications/{owned.id}/read"
        )
        self.assertEqual(marked.status_code, 200)
        self.assertEqual(
            marked.json()["message"],
            "Notification marked as read",
        )
        read_response = self.client.get(
            "/reminders/notifications?unread_only=true"
        )
        self.assertEqual(
            [item["id"] for item in read_response.json()],
            [unread.id],
        )

        foreign_mark = self.client.patch(
            f"/reminders/notifications/{foreign_notification.id}/read"
        )
        self.assertEqual(foreign_mark.status_code, 404)

    def test_add_months_clamps_month_end(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))


if __name__ == "__main__":
    unittest.main()
