from datetime import date
from typing import TypedDict

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.expense import Expense
from app.models.service_record import ServiceRecord
from app.models.vehicle import Vehicle
from app.schemas.service_history import (
    ServiceRecordCreate,
    ServiceRecordUpdate,
)


class ServiceRecordResult(TypedDict):
    duplicate: bool
    record: ServiceRecord


def _commit(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def get_user_vehicle(
    db: Session,
    vehicle_id: int,
    user_id: int,
) -> Vehicle | None:
    return (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id,
            Vehicle.user_id == user_id,
        )
        .first()
    )


def find_duplicate_service(
    db: Session,
    vehicle_id: int,
    service_date: date,
    odometer_reading: float,
    service_type: str,
    exclude_record_id: int | None = None,
) -> ServiceRecord | None:
    normalized_type = service_type.strip().lower()
    query = db.query(ServiceRecord).filter(
        ServiceRecord.vehicle_id == vehicle_id,
        ServiceRecord.service_date == service_date,
        ServiceRecord.odometer_reading == odometer_reading,
        func.lower(func.trim(ServiceRecord.service_type)) == normalized_type,
    )

    if exclude_record_id is not None:
        query = query.filter(ServiceRecord.id != exclude_record_id)

    return query.first()


def create_service_record(
    db: Session,
    vehicle_id: int,
    data: ServiceRecordCreate,
) -> ServiceRecordResult:
    duplicate = find_duplicate_service(
        db=db,
        vehicle_id=vehicle_id,
        service_date=data.service_date,
        odometer_reading=data.odometer_reading,
        service_type=data.service_type,
    )
    if duplicate is not None:
        return {"duplicate": True, "record": duplicate}

    record = ServiceRecord(
        vehicle_id=vehicle_id,
        service_date=data.service_date,
        odometer_reading=data.odometer_reading,
        service_type=data.service_type,
        description=data.description,
        workshop_name=data.workshop_name,
        total_cost=data.total_cost,
        source_type="manual",
        source_document_id=None,
    )
    db.add(record)
    _commit(db)
    db.refresh(record)
    return {"duplicate": False, "record": record}


def create_invoice_service_record(
    db: Session,
    document: Document,
    data: ServiceRecordCreate,
) -> ServiceRecordResult:
    if document.vehicle_id is None:
        raise ValueError("Document is not associated with a vehicle")

    existing_document_record = (
        db.query(ServiceRecord)
        .filter(ServiceRecord.source_document_id == document.id)
        .first()
    )
    if existing_document_record is not None:
        return {"duplicate": True, "record": existing_document_record}

    duplicate = find_duplicate_service(
        db=db,
        vehicle_id=document.vehicle_id,
        service_date=data.service_date,
        odometer_reading=data.odometer_reading,
        service_type=data.service_type,
    )
    if duplicate is not None:
        return {"duplicate": True, "record": duplicate}

    record = ServiceRecord(
        vehicle_id=document.vehicle_id,
        source_document_id=document.id,
        service_date=data.service_date,
        odometer_reading=data.odometer_reading,
        service_type=data.service_type,
        description=data.description,
        workshop_name=data.workshop_name,
        total_cost=data.total_cost,
        source_type="invoice",
    )
    db.add(record)
    db.flush()
    return {"duplicate": False, "record": record}


def get_vehicle_service_history(
    db: Session,
    vehicle_id: int,
) -> list[ServiceRecord]:
    return (
        db.query(ServiceRecord)
        .filter(ServiceRecord.vehicle_id == vehicle_id)
        .order_by(
            ServiceRecord.service_date.desc(),
            ServiceRecord.id.desc(),
        )
        .all()
    )


def get_service_record(
    db: Session,
    record_id: int,
    user_id: int,
) -> ServiceRecord | None:
    return (
        db.query(ServiceRecord)
        .join(Vehicle, ServiceRecord.vehicle_id == Vehicle.id)
        .filter(
            ServiceRecord.id == record_id,
            Vehicle.user_id == user_id,
        )
        .first()
    )


def update_service_record(
    db: Session,
    record: ServiceRecord,
    data: ServiceRecordUpdate,
) -> ServiceRecordResult:
    update_data = data.model_dump(exclude_unset=True)
    non_nullable_fields = {
        "service_date",
        "odometer_reading",
        "service_type",
        "total_cost",
    }
    if any(
        field in update_data and update_data[field] is None
        for field in non_nullable_fields
    ):
        raise ValueError("Non-nullable service fields cannot be cleared")

    candidate = {
        "service_date": record.service_date,
        "odometer_reading": record.odometer_reading,
        "service_type": record.service_type,
    }
    candidate.update(
        {
            key: value
            for key, value in update_data.items()
            if key in candidate
        }
    )

    duplicate = find_duplicate_service(
        db=db,
        vehicle_id=record.vehicle_id,
        service_date=candidate["service_date"],
        odometer_reading=candidate["odometer_reading"],
        service_type=candidate["service_type"],
        exclude_record_id=record.id,
    )
    if duplicate is not None:
        return {"duplicate": True, "record": duplicate}

    for field, value in update_data.items():
        setattr(record, field, value)

    _commit(db)
    db.refresh(record)
    return {"duplicate": False, "record": record}


def delete_service_record(
    db: Session,
    record: ServiceRecord,
) -> None:
    expenses = (
        db.query(Expense)
        .filter(Expense.service_record_id == record.id)
        .all()
    )
    for expense in expenses:
        expense.service_record_id = None

    db.delete(record)
    _commit(db)
