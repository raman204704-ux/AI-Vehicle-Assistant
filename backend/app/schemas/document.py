from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    vehicle_id: int
    file_name: str
    file_type: str
    file_size: int | None
    document_type: str | None
    processing_status: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)
