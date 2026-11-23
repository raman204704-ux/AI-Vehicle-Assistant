from dataclasses import dataclass
from pathlib import PurePosixPath

from fastapi import UploadFile

MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

_SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


class FileValidationError(ValueError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ValidatedUpload:
    content: bytes
    file_name: str
    file_type: str
    file_size: int


def detect_file_type(content: bytes) -> str | None:
    for signature, file_type in _SIGNATURES:
        if content.startswith(signature):
            return file_type
    return None


def validate_upload_file(file: UploadFile) -> ValidatedUpload:
    if not file.filename:
        raise FileValidationError(400, "Filename is required.")

    raw_name = file.filename.replace("\\", "/")
    filename = PurePosixPath(raw_name).name
    filename = "".join(char for char in filename if char.isprintable()).strip()
    if not filename:
        raise FileValidationError(400, "Filename is required.")

    extension = PurePosixPath(filename).suffix.lower()
    expected_type = ALLOWED_EXTENSIONS.get(extension)
    if expected_type is None:
        raise FileValidationError(415, "Unsupported file format.")

    try:
        content = file.file.read(MAX_FILE_SIZE + 1)
    finally:
        file.file.seek(0)

    if not content:
        raise FileValidationError(400, "Uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE:
        raise FileValidationError(413, "File size exceeds 10 MB limit.")

    detected_type = detect_file_type(content)
    if detected_type is None:
        raise FileValidationError(415, "Invalid or unsupported file content.")
    if detected_type != expected_type:
        raise FileValidationError(
            415,
            "File extension does not match actual file content.",
        )

    return ValidatedUpload(
        content=content,
        file_name=filename[:255],
        file_type=detected_type,
        file_size=len(content),
    )
