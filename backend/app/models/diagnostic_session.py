from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'closed')",
            name="ck_diagnostic_sessions_valid_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            name="fk_diagnostic_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    vehicle_id = Column(
        Integer,
        ForeignKey(
            "vehicles.id",
            name="fk_diagnostic_sessions_vehicle_id_vehicles",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=True)
    status = Column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )
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

    messages = relationship(
        "DiagnosticMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(DiagnosticMessage.created_at, DiagnosticMessage.id)",
    )
