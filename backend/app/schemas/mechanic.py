from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.assistant import SourceResponse


class MechanicQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    session_id: int | None = Field(default=None, gt=0)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Question must not be blank")
        return normalized


class DiagnosticMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagnosticSessionResponse(BaseModel):
    id: int
    vehicle_id: int
    title: str | None
    status: Literal["active", "closed"]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MechanicResponse(BaseModel):
    session_id: int
    answer: str
    sources: list[SourceResponse]
    created_at: datetime
