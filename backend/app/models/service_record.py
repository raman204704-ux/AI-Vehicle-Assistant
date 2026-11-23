from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class ServiceRecord(Base):
    __tablename__ = "service_records"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            name="uq_service_records_source_document_id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    source_document_id = Column(
        Integer,
        ForeignKey(
            "documents.id",
            name="fk_service_records_source_document_id_documents",
        ),
        nullable=True,
    )
    service_date = Column(Date, nullable=False)
    odometer_reading = Column(Float, nullable=False)
    service_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    workshop_name = Column(String(150), nullable=True)
    total_cost = Column(Float, nullable=False, default=0)
    source_type = Column(
        String(20),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="service_records")
