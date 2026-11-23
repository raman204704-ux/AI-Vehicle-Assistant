import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.mechanic import (
    DiagnosticMessageResponse,
    DiagnosticSessionResponse,
    MechanicQuestion,
    MechanicResponse,
)
from app.services.mechanic_service import (
    MechanicNotFoundError,
    MechanicService,
)
from app.services.rag.dependencies import get_rag_service
from app.services.rag.errors import RAGError
from app.services.rag.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/mechanic",
    tags=["AI Mechanic Assistant"],
)


@router.post(
    "/vehicles/{vehicle_id}/ask",
    response_model=MechanicResponse,
)
def ask_mechanic(
    vehicle_id: int,
    request: MechanicQuestion,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
) -> MechanicResponse:
    service = MechanicService(db, rag_service)
    try:
        return MechanicResponse.model_validate(
            service.ask_mechanic(
                vehicle_id=vehicle_id,
                user_id=current_user.id,
                question=request.question,
                session_id=request.session_id,
            )
        )
    except MechanicNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except RAGError as error:
        logger.warning("AI mechanic request failed: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


@router.get(
    "/vehicles/{vehicle_id}/sessions",
    response_model=list[DiagnosticSessionResponse],
)
def get_diagnostic_sessions(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DiagnosticSessionResponse]:
    try:
        sessions = MechanicService(db).list_sessions(
            vehicle_id=vehicle_id, user_id=current_user.id
        )
        return [
            DiagnosticSessionResponse.model_validate(session)
            for session in sessions
        ]
    except MechanicNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[DiagnosticMessageResponse],
)
def get_diagnostic_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DiagnosticMessageResponse]:
    try:
        messages = MechanicService(db).get_messages(
            session_id=session_id, user_id=current_user.id
        )
        return [
            DiagnosticMessageResponse.model_validate(message)
            for message in messages
        ]
    except MechanicNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
