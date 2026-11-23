import logging
import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.file_validation import validate_upload_file
from app.models.document import Document
from app.models.vehicle import Vehicle

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = settings.upload_dir
if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR
UPLOAD_DIR = UPLOAD_DIR.resolve()


def create_upload_directory() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_document(content: bytes, file_type: str) -> dict[str, str]:
    extension_map = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }
    extension = extension_map.get(file_type)
    if extension is None:
        raise ValueError("Unsupported file type")

    create_upload_directory()
    for _ in range(3):
        unique_filename = f"{uuid.uuid4()}{extension}"
        file_path = UPLOAD_DIR / unique_filename
        try:
            with file_path.open("xb") as document:
                document.write(content)
        except FileExistsError:
            continue
        except OSError:
            file_path.unlink(missing_ok=True)
            raise

        return {
            "file_name": unique_filename,
            "file_path": str(file_path.resolve()),
        }

    raise FileExistsError("Could not allocate a unique document filename.")


def delete_document_file(file_path: str) -> None:
    path = Path(file_path).resolve()
    if path.parent != UPLOAD_DIR.resolve():
        raise ValueError("Invalid document storage path")
    if path.exists() and path.is_file():
        path.unlink()


def move_document_to_trash(file_path: str) -> str | None:
    storage_directory = UPLOAD_DIR.resolve()
    original_path = Path(file_path).resolve()
    if original_path.parent != storage_directory:
        raise ValueError("Invalid document storage path")

    if not original_path.exists():
        return None
    if not original_path.is_file():
        raise ValueError("Invalid document file")

    trash_path = storage_directory / (
        f".deleting-{uuid.uuid4().hex}{original_path.suffix}"
    )
    os.replace(original_path, trash_path)
    return str(trash_path)


def restore_document_from_trash(trash_path: str, original_path: str) -> None:
    storage_directory = UPLOAD_DIR.resolve()
    trash = Path(trash_path).resolve()
    original = Path(original_path).resolve()

    if trash.parent != storage_directory or original.parent != storage_directory:
        raise ValueError("Invalid document storage path")

    if trash.exists():
        os.replace(trash, original)


def upload_document(
    db: Session,
    vehicle: Vehicle,
    upload: UploadFile,
    document_type: str | None,
) -> Document:
    validated_upload = validate_upload_file(upload)
    stored_file = save_document(
        validated_upload.content,
        validated_upload.file_type,
    )
    document = Document(
        vehicle_id=vehicle.id,
        file_name=validated_upload.file_name,
        file_path=stored_file["file_path"],
        file_type=validated_upload.file_type,
        file_size=validated_upload.file_size,
        document_type=document_type,
        processing_status="uploaded",
    )
    try:
        db.add(document)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        try:
            delete_document_file(stored_file["file_path"])
        except (OSError, ValueError):
            logger.exception("Failed to clean up document after database failure")
        raise

    db.refresh(document)
    return document
