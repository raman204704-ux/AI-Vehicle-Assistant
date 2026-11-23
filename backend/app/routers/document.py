import logging
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.file_validation import FileValidationError
from app.database.connection import get_db
from app.models.document import Document
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.document import DocumentResponse
from app.services.document_service import (
    UPLOAD_DIR,
    delete_document_file,
    move_document_to_trash,
    restore_document_from_trash,
    upload_document,
)
from app.services.invoice_processing_service import (
    process_document_in_background,
    should_process_invoice,
)

logger = logging.getLogger(__name__)

download_router = APIRouter(
    prefix="/documents",
    tags=["Document Management"],
)

router = APIRouter(
    prefix="/vehicles/{vehicle_id}/documents",
    tags=["Document Management"],
)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_vehicle_document(
    vehicle_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None, max_length=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id,
            Vehicle.user_id == current_user.id,
        )
        .first()
    )
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    if document_type is not None:
        document_type = document_type.strip() or None

    try:
        document = upload_document(db, vehicle, file, document_type)
        if should_process_invoice(document.document_type):
            background_tasks.add_task(
                process_document_in_background,
                document.id,
            )
        return document
    except FileValidationError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error
    except (OSError, ValueError) as error:
        logger.exception("Document file storage failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store the uploaded document",
        ) from error
    except SQLAlchemyError as error:
        logger.exception("Document metadata insertion failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save document information",
        ) from error


@router.get("", response_model=list[DocumentResponse])
def get_vehicle_documents(
    vehicle_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Document]:
    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id,
            Vehicle.user_id == current_user.id,
        )
        .first()
    )
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return (
        db.query(Document)
        .filter(Document.vehicle_id == vehicle_id)
        .order_by(Document.uploaded_at.desc(), Document.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@download_router.get(
    "/{document_id}/download",
    response_class=FileResponse,
)
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    document = (
        db.query(Document)
        .join(Vehicle, Document.vehicle_id == Vehicle.id)
        .filter(
            Document.id == document_id,
            Vehicle.user_id == current_user.id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        storage_directory = UPLOAD_DIR.resolve(strict=True)
        file_path = Path(document.file_path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        ) from error

    if file_path.parent != storage_directory or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Document file not found")

    download_name = Path(document.file_name.replace("\\", "/")).name
    download_name = "".join(
        character
        for character in download_name
        if character >= " " and character != "\x7f"
    ).strip()
    if not download_name:
        download_name = f"document-{document.id}"

    return FileResponse(
        path=file_path,
        media_type=document.file_type,
        filename=download_name,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@download_router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    document = (
        db.query(Document)
        .join(Vehicle, Document.vehicle_id == Vehicle.id)
        .filter(
            Document.id == document_id,
            Vehicle.user_id == current_user.id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    original_path = document.file_path
    try:
        trash_path = move_document_to_trash(original_path)
    except (OSError, ValueError) as error:
        logger.exception("Could not prepare document for deletion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not prepare document for deletion",
        ) from error

    try:
        db.delete(document)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        if trash_path is not None:
            try:
                restore_document_from_trash(trash_path, original_path)
            except (OSError, ValueError):
                logger.exception(
                    "Could not restore document after database failure"
                )
        logger.exception("Document database deletion failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete document",
        ) from error

    if trash_path is not None:
        try:
            delete_document_file(trash_path)
        except (OSError, ValueError):
            logger.exception(
                "Document record deleted, but temporary file cleanup failed"
            )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
