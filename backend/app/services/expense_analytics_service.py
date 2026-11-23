from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.service_record import ServiceRecord
from app.models.vehicle import Vehicle


def get_expense_summary(db: Session, vehicle_id: int) -> dict:
    result = (
        db.query(
            func.coalesce(func.sum(Expense.amount), 0),
            func.count(Expense.id),
            func.coalesce(func.avg(Expense.amount), 0),
        )
        .filter(Expense.vehicle_id == vehicle_id)
        .first()
    )

    return {
        "vehicle_id": vehicle_id,
        "total_expenses": float(result[0]),
        "total_transactions": result[1],
        "average_expense": round(float(result[2]), 2),
    }


def get_category_expenses(db: Session, vehicle_id: int) -> list[dict]:
    results = (
        db.query(
            Expense.category,
            func.sum(Expense.amount).label("total_amount"),
            func.count(Expense.id).label("transaction_count"),
        )
        .filter(Expense.vehicle_id == vehicle_id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    return [
        {
            "category": row.category,
            "total_amount": float(row.total_amount),
            "transaction_count": row.transaction_count,
        }
        for row in results
    ]


def get_monthly_expenses(db: Session, vehicle_id: int) -> list[dict]:
    year_expression = extract("year", Expense.expense_date)
    month_expression = extract("month", Expense.expense_date)
    results = (
        db.query(
            year_expression.label("year"),
            month_expression.label("month"),
            func.sum(Expense.amount).label("total_amount"),
        )
        .filter(Expense.vehicle_id == vehicle_id)
        .group_by(year_expression, month_expression)
        .order_by(year_expression, month_expression)
        .all()
    )

    return [
        {
            "year": int(row.year),
            "month": int(row.month),
            "total_amount": float(row.total_amount),
        }
        for row in results
    ]


def get_yearly_expenses(db: Session, vehicle_id: int) -> list[dict]:
    year_expression = extract("year", Expense.expense_date)
    results = (
        db.query(
            year_expression.label("year"),
            func.sum(Expense.amount).label("total_amount"),
        )
        .filter(Expense.vehicle_id == vehicle_id)
        .group_by(year_expression)
        .order_by(year_expression)
        .all()
    )

    return [
        {
            "year": int(row.year),
            "total_amount": float(row.total_amount),
        }
        for row in results
    ]


def get_service_type_expenses(db: Session, vehicle_id: int) -> list[dict]:
    results = (
        db.query(
            func.coalesce(
                ServiceRecord.service_type,
                "Unlinked / not specified",
            ).label("service_type"),
            func.sum(Expense.amount).label("total_amount"),
            func.count(Expense.id).label("transaction_count"),
        )
        .outerjoin(
            ServiceRecord,
            (Expense.service_record_id == ServiceRecord.id)
            & (Expense.vehicle_id == ServiceRecord.vehicle_id),
        )
        .filter(Expense.vehicle_id == vehicle_id)
        .group_by(ServiceRecord.service_type)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    return [
        {
            "service_type": row.service_type,
            "total_amount": float(row.total_amount),
            "transaction_count": row.transaction_count,
        }
        for row in results
    ]


def compare_vehicle_expenses(db: Session, user_id: int) -> list[dict]:
    results = (
        db.query(
            Vehicle.id,
            Vehicle.vehicle_name,
            func.coalesce(func.sum(Expense.amount), 0).label(
                "total_expenses"
            ),
        )
        .outerjoin(Expense, Vehicle.id == Expense.vehicle_id)
        .filter(Vehicle.user_id == user_id)
        .group_by(Vehicle.id, Vehicle.vehicle_name)
        .order_by(Vehicle.vehicle_name)
        .all()
    )

    return [
        {
            "vehicle_id": row.id,
            "vehicle_name": row.vehicle_name,
            "total_expenses": float(row.total_expenses),
        }
        for row in results
    ]
