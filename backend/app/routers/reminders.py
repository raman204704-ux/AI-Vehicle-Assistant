from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.reminder import (
    NotificationResponse,
    ReminderCreate,
    ReminderResponse,
    ReminderUpdate,
)
from app.services.reminder_service import (
    ReminderInputError,
    ReminderNotFoundError,
    ReminderService,
    ReminderStateError,
)

router = APIRouter(prefix="/reminders", tags=["Maintenance Reminders"])


@router.post(
    "/vehicles/{vehicle_id}",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reminder(
    vehicle_id: int,
    request: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    try:
        return ReminderService(db).create_reminder(
            vehicle_id=vehicle_id,
            user_id=current_user.id,
            data=request,
        )
    except ReminderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=list[ReminderResponse],
)
def get_reminders(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReminderResponse]:
    try:
        return ReminderService(db).get_reminders(
            vehicle_id=vehicle_id,
            user_id=current_user.id,
        )
    except ReminderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.patch(
    "/{reminder_id}",
    response_model=ReminderResponse,
)
def update_reminder(
    reminder_id: int,
    request: ReminderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    try:
        return ReminderService(db).update_reminder(
            reminder_id=reminder_id,
            user_id=current_user.id,
            data=request,
        )
    except ReminderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ReminderInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.post(
    "/{reminder_id}/complete",
    response_model=ReminderResponse,
)
def complete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    try:
        return ReminderService(db).complete_reminder(
            reminder_id=reminder_id,
            user_id=current_user.id,
        )
    except ReminderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ReminderInputError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except ReminderStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        ReminderService(db).cancel_reminder(
            reminder_id=reminder_id,
            user_id=current_user.id,
        )
    except ReminderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ReminderStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "/notifications",
    response_model=list[NotificationResponse],
)
def get_notifications(
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NotificationResponse]:
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id
    )
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return (
        query.order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(limit)
        .all()
    )


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    notification.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}
