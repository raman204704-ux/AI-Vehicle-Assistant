from sqlalchemy import Boolean, Column, DateTime, Integer, String, true
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vehicles = relationship(
        "Vehicle",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
