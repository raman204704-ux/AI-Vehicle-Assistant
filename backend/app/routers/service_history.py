from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.service_history import (
    ServiceRecordCreate,
    ServiceRecordResponse,
    ServiceRecordUpdate,
)
from app.services import service_history_service as service

router = APIRouter(tags=["Service History"])


@router.post(
    "/vehicles/{vehicle_id}/service-records",
    response_model=ServiceRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_record(
    vehicle_id: int,
    data: ServiceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ServiceRecordResponse:
    vehicle = service.get_user_vehicle(db, vehicle_id, current_user.id)
    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found",
        )

    result = service.create_service_record(db, vehicle_id, data)
    if result["duplicate"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Possible duplicate service record",
                "existing_record_id": result["record"].id,
            },
        )
    return result["record"]


@router.get(
    "/vehicles/{vehicle_id}/service-records",
    response_model=list[ServiceRecordResponse],
)
def get_vehicle_service_history(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ServiceRecordResponse]:
    vehicle = service.get_user_vehicle(db, vehicle_id, current_user.id)
    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found",
        )
    return service.get_vehicle_service_history(db, vehicle_id)


@router.get(
    "/service-records/{record_id}",
    response_model=ServiceRecordResponse,
)
def get_service_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ServiceRecordResponse:
    record = service.get_service_record(db, record_id, current_user.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service record not found",
        )
    return record


@router.put(
    "/service-records/{record_id}",
    response_model=ServiceRecordResponse,
)
def update_service_record(
    record_id: int,
    data: ServiceRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ServiceRecordResponse:
    record = service.get_service_record(db, record_id, current_user.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service record not found",
        )

    result = service.update_service_record(db, record, data)
    if result["duplicate"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Update would create a duplicate record",
                "existing_record_id": result["record"].id,
            },
        )
    return result["record"]


@router.delete(
    "/service-records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_service_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    record = service.get_service_record(db, record_id, current_user.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service record not found",
        )

    service.delete_service_record(db, record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
