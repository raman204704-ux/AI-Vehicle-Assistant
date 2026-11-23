from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", name="fk_vehicles_user_id_users"),
        nullable=True,
        index=True,
    )
    vehicle_name = Column(String(100), nullable=False)
    manufacturer = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    fuel_type = Column(String(30), nullable=False)
    registration_number = Column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )
    current_odometer = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="vehicles")
    service_records = relationship(
        "ServiceRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "Document",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
    expenses = relationship(
        "Expense",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
