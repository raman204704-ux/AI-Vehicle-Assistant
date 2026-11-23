from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.database.connection import Base


class MaintenanceReminder(Base):
    __tablename__ = "maintenance_reminders"
    __table_args__ = (
        CheckConstraint(
            "status != 'active' OR due_date IS NOT NULL "
            "OR due_odometer IS NOT NULL",
            name="ck_maintenance_reminders_has_due",
        ),
        CheckConstraint(
            "repeat_interval_months IS NULL OR repeat_interval_months > 0",
            name="ck_maintenance_reminders_months_positive",
        ),
        CheckConstraint(
            "repeat_interval_km IS NULL OR repeat_interval_km > 0",
            name="ck_maintenance_reminders_km_positive",
        ),
        CheckConstraint(
            "reminder_days_before BETWEEN 0 AND 365",
            name="ck_maintenance_reminders_days_before_range",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')",
            name="ck_maintenance_reminders_valid_status",
        ),
        Index(
            "ix_maintenance_reminders_schedule",
            "status",
            "is_enabled",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            name="fk_maintenance_reminders_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    vehicle_id = Column(
        Integer,
        ForeignKey(
            "vehicles.id",
            name="fk_maintenance_reminders_vehicle_id_vehicles",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False)
    due_date = Column(Date, nullable=True)
    due_odometer = Column(Float, nullable=True)
    repeat_interval_months = Column(Integer, nullable=True)
    repeat_interval_km = Column(Float, nullable=True)
    reminder_days_before = Column(Integer, nullable=False, default=7)
    status = Column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
