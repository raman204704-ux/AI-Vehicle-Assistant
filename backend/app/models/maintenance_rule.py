from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.database.connection import Base


class MaintenanceRule(Base):
    __tablename__ = "maintenance_rules"
    __table_args__ = (
        CheckConstraint(
            "interval_km IS NULL OR interval_km > 0",
            name="ck_maintenance_rules_interval_km_positive",
        ),
        CheckConstraint(
            "interval_months IS NULL OR interval_months > 0",
            name="ck_maintenance_rules_interval_months_positive",
        ),
        CheckConstraint(
            "interval_km IS NOT NULL OR interval_months IS NOT NULL",
            name="ck_maintenance_rules_has_interval",
        ),
        CheckConstraint(
            "model_year_min IS NULL OR model_year_max IS NULL "
            "OR model_year_min <= model_year_max",
            name="ck_maintenance_rules_valid_model_year_range",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    maintenance_type = Column(String(100), nullable=False, index=True)
    service_type = Column(String(100), nullable=False)
    manufacturer = Column(String(100), nullable=True, index=True)
    model = Column(String(100), nullable=True, index=True)
    fuel_type = Column(String(30), nullable=True)
    model_year_min = Column(Integer, nullable=True)
    model_year_max = Column(Integer, nullable=True)
    interval_km = Column(Integer, nullable=True)
    interval_months = Column(Integer, nullable=True)
    source_title = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=False)
    effective_date = Column(Date, nullable=True)
    verified_at = Column(Date, nullable=False)
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
