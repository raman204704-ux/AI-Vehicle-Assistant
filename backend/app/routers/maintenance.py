from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.maintenance import MaintenancePredictionResponse
from app.services.maintenance_prediction_service import (
    get_maintenance_predictions,
)

router = APIRouter(
    prefix="/maintenance",
    tags=["Maintenance Prediction"],
)


@router.get(
    "/vehicles/{vehicle_id}/predictions",
    response_model=MaintenancePredictionResponse,
)
def predict_vehicle_maintenance(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenancePredictionResponse:
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

    return get_maintenance_predictions(db, vehicle)
