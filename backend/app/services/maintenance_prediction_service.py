from datetime import date, datetime, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.maintenance_rule import MaintenanceRule
from app.models.service_record import ServiceRecord
from app.models.vehicle import Vehicle


def normalize(value: str) -> str:
    return value.strip().casefold()


def get_applicable_rules(
    db: Session,
    vehicle: Vehicle,
    as_of: date | None = None,
) -> list[MaintenanceRule]:
    effective_on = as_of or date.today()
    rules = (
        db.query(MaintenanceRule)
        .filter(MaintenanceRule.is_active.is_(True))
        .all()
    )
    applicable_rules: list[MaintenanceRule] = []

    for rule in rules:
        if (
            rule.effective_date is not None
            and rule.effective_date > effective_on
        ):
            continue
        if (
            rule.manufacturer
            and normalize(rule.manufacturer) != normalize(vehicle.manufacturer)
        ):
            continue
        if rule.model and normalize(rule.model) != normalize(vehicle.model):
            continue
        if (
            rule.fuel_type
            and normalize(rule.fuel_type) != normalize(vehicle.fuel_type)
        ):
            continue
        if (
            rule.model_year_min is not None
            and vehicle.year < rule.model_year_min
        ):
            continue
        if (
            rule.model_year_max is not None
            and vehicle.year > rule.model_year_max
        ):
            continue
        applicable_rules.append(rule)

    return applicable_rules


def get_last_service(
    db: Session,
    vehicle_id: int,
    service_type: str,
) -> ServiceRecord | None:
    return (
        db.query(ServiceRecord)
        .filter(
            ServiceRecord.vehicle_id == vehicle_id,
            func.lower(func.trim(ServiceRecord.service_type))
            == normalize(service_type),
        )
        .order_by(
            ServiceRecord.service_date.desc(),
            ServiceRecord.id.desc(),
        )
        .first()
    )


def calculate_prediction(
    rule: MaintenanceRule,
    last_service: ServiceRecord | None,
    current_odometer: float,
    today: date,
) -> dict[str, object]:
    last_date = last_service.service_date if last_service is not None else None
    last_odometer = (
        last_service.odometer_reading if last_service is not None else None
    )
    next_due_odometer: float | None = None
    remaining_km: float | None = None
    next_due_date: date | None = None
    remaining_days: int | None = None
    statuses: list[str] = []

    if rule.interval_km is not None:
        if rule.interval_km <= 0 or last_service is None:
            statuses.append("unknown")
        elif last_odometer is None or last_odometer > current_odometer:
            statuses.append("unknown")
        else:
            next_due_odometer = last_odometer + rule.interval_km
            remaining_km = next_due_odometer - current_odometer
            if remaining_km <= 0:
                statuses.append("overdue")
            elif remaining_km <= rule.interval_km * 0.10:
                statuses.append("due_soon")
            else:
                statuses.append("not_due")

    if rule.interval_months is not None:
        if rule.interval_months <= 0 or last_date is None:
            statuses.append("unknown")
        else:
            next_due_date = last_date + relativedelta(
                months=rule.interval_months
            )
            remaining_days = (next_due_date - today).days
            if remaining_days <= 0:
                statuses.append("overdue")
            elif remaining_days <= max(
                30,
                rule.interval_months * 30 * 0.10,
            ):
                statuses.append("due_soon")
            else:
                statuses.append("not_due")

    if "overdue" in statuses:
        final_status = "overdue"
    elif "unknown" in statuses or not statuses:
        final_status = "unknown"
    elif "due_soon" in statuses:
        final_status = "due_soon"
    else:
        final_status = "not_due"

    return {
        "rule_id": rule.id,
        "maintenance_type": rule.maintenance_type,
        "status": final_status,
        "last_service_date": last_date,
        "last_service_odometer": last_odometer,
        "current_odometer": current_odometer,
        "next_due_odometer": next_due_odometer,
        "remaining_km": remaining_km,
        "next_due_date": next_due_date,
        "remaining_days": remaining_days,
        "source_title": rule.source_title,
        "source_url": rule.source_url,
    }


def get_maintenance_predictions(
    db: Session,
    vehicle: Vehicle,
    today: date | None = None,
) -> dict[str, object]:
    evaluation_date = today or date.today()
    rules = get_applicable_rules(db, vehicle, as_of=evaluation_date)
    predictions = []

    for rule in rules:
        last_service = get_last_service(
            db,
            vehicle.id,
            rule.service_type,
        )
        predictions.append(
            calculate_prediction(
                rule=rule,
                last_service=last_service,
                current_odometer=vehicle.current_odometer,
                today=evaluation_date,
            )
        )

    return {
        "vehicle_id": vehicle.id,
        "vehicle_name": vehicle.vehicle_name,
        "current_odometer": vehicle.current_odometer,
        "predictions": predictions,
        "generated_at": datetime.now(timezone.utc),
    }
