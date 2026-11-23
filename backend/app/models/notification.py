from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database.connection import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_notifications_user_idempotency",
        ),
        CheckConstraint(
            "notification_type IN ('upcoming', 'overdue')",
            name="ck_notifications_valid_type",
        ),
        Index(
            "ix_notifications_user_created_at",
            "user_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            name="fk_notifications_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    vehicle_id = Column(
        Integer,
        ForeignKey(
            "vehicles.id",
            name="fk_notifications_vehicle_id_vehicles",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    reminder_id = Column(
        Integer,
        ForeignKey(
            "maintenance_reminders.id",
            name="fk_notifications_reminder_id_maintenance_reminders",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
