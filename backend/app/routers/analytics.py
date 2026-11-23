from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.analytics import (
    CategoryExpense,
    ExpenseSummary,
    MonthlyExpense,
    ServiceTypeExpense,
    VehicleExpenseComparison,
    YearlyExpense,
)
from app.services.expense_analytics_service import (
    compare_vehicle_expenses,
    get_category_expenses,
    get_expense_summary,
    get_monthly_expenses,
    get_service_type_expenses,
    get_yearly_expenses,
)

router = APIRouter(
    prefix="/analytics",
    tags=["Expense Analytics"],
)


def verify_vehicle_ownership(
    vehicle_id: int,
    current_user: User,
    db: Session,
) -> None:
    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id,
            Vehicle.user_id == current_user.id,
        )
        .first()
    )
    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found",
        )


@router.get(
    "/vehicles/{vehicle_id}/summary",
    response_model=ExpenseSummary,
)
def expense_summary(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpenseSummary:
    verify_vehicle_ownership(vehicle_id, current_user, db)
    return get_expense_summary(db, vehicle_id)


@router.get(
    "/vehicles/{vehicle_id}/categories",
    response_model=list[CategoryExpense],
)
def category_expenses(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CategoryExpense]:
    verify_vehicle_ownership(vehicle_id, current_user, db)
    return get_category_expenses(db, vehicle_id)


@router.get(
    "/vehicles/{vehicle_id}/monthly",
    response_model=list[MonthlyExpense],
)
def monthly_expenses(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MonthlyExpense]:
    verify_vehicle_ownership(vehicle_id, current_user, db)
    return get_monthly_expenses(db, vehicle_id)


@router.get(
    "/vehicles/{vehicle_id}/yearly",
    response_model=list[YearlyExpense],
)
def yearly_expenses(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[YearlyExpense]:
    verify_vehicle_ownership(vehicle_id, current_user, db)
    return get_yearly_expenses(db, vehicle_id)


@router.get(
    "/vehicles/{vehicle_id}/services",
    response_model=list[ServiceTypeExpense],
)
def service_expenses(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ServiceTypeExpense]:
    verify_vehicle_ownership(vehicle_id, current_user, db)
    return get_service_type_expenses(db, vehicle_id)


@router.get(
    "/expenses/comparison",
    response_model=list[VehicleExpenseComparison],
)
def vehicle_expense_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[VehicleExpenseComparison]:
    return compare_vehicle_expenses(db, current_user.id)
