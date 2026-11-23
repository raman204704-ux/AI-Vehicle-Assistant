import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.assistant import AssistantResponse, VehicleQuestion
from app.services.rag.dependencies import get_rag_service
from app.services.rag.errors import RAGError
from app.services.rag.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/assistant",
    tags=["AI Vehicle Assistant"],
)

@router.post(
    "/vehicles/{vehicle_id}/ask",
    response_model=AssistantResponse,
)
def ask_vehicle_question(
    vehicle_id: int,
    request: VehicleQuestion,
    service: RAGService = Depends(get_rag_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantResponse:
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

    vehicle_context = {
        "id": vehicle.id,
        "manufacturer": vehicle.manufacturer,
        "model": vehicle.model,
        "year": vehicle.year,
        "fuel_type": vehicle.fuel_type,
        "engine": request.engine,
        "market": request.market,
    }

    try:
        return AssistantResponse.model_validate(
            service.ask(request.question, vehicle_context)
        )
    except RAGError as error:
        logger.warning("Vehicle maintenance assistant request failed: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
