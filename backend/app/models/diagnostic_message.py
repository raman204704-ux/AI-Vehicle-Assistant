from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class DiagnosticMessage(Base):
    __tablename__ = "diagnostic_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_diagnostic_messages_valid_role",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey(
            "diagnostic_sessions.id",
            name="fk_diagnostic_messages_session_id_sessions",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session = relationship(
        "DiagnosticSession",
        back_populates="messages",
    )
