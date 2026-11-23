from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class VehicleQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    engine: str | None = Field(default=None, max_length=100)
    market: str | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Question must not be blank")
        return normalized

    @field_validator("engine", "market")
    @classmethod
    def optional_vehicle_detail_must_not_be_blank(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SourceResponse(BaseModel):
    source_id: str
    title: str
    url: str
    source_type: str
    retrieved_at: datetime


class AssistantResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceResponse]
    documents_retrieved: int = Field(ge=0)
    documents_indexed: int = Field(ge=0)
    generated_at: datetime
