from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vehicle Maintenance Assistant"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./vehicle_maintenance.db"
    secret_key: SecretStr = Field(min_length=32)
    algorithm: str = "HS256"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    access_token_expire_minutes: int = Field(default=30, gt=0)
    upload_dir: Path = Path("uploads/documents")
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    tavily_api_key: SecretStr | None = None
    redis_url: str = "redis://localhost:6379/0"
    reminder_mileage_threshold_km: float = Field(default=500, ge=0)
    chroma_persist_directory: Path = Path("storage/chroma")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rag_max_search_results: int = Field(default=7, gt=0, le=10)
    rag_min_source_characters: int = Field(default=200, gt=0)
    rag_max_source_characters: int = Field(default=30000, gt=0)
    rag_chunk_size_words: int = Field(default=220, gt=0)
    rag_chunk_overlap_words: int = Field(default=40, ge=0)
    rag_retrieval_limit: int = Field(default=10, gt=0, le=30)
    rag_result_limit: int = Field(default=5, gt=0, le=10)
    rag_max_context_characters: int = Field(default=24000, gt=0)
    rag_cache_ttl_days: int = Field(default=30, gt=0)
    rag_max_cosine_distance: float = Field(default=0.65, gt=0, le=2)
    ocr_lang: str = "en"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_runtime_configuration(self) -> None:
        if self.app_env != "production":
            return

        origins = [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]
        if not origins or "*" in origins:
            raise ValueError(
                "Production CORS_ORIGINS must contain explicit HTTPS origins"
            )
        for origin in origins:
            try:
                parsed_origin = urlsplit(origin)
            except ValueError as error:
                raise ValueError(
                    "Production CORS_ORIGINS must contain explicit HTTPS origins"
                ) from error
            if (
                parsed_origin.scheme != "https"
                or not parsed_origin.hostname
                or parsed_origin.username is not None
                or parsed_origin.password is not None
                or parsed_origin.path
                or parsed_origin.query
                or parsed_origin.fragment
            ):
                raise ValueError(
                    "Production CORS_ORIGINS must contain explicit HTTPS origins"
                )
            try:
                parsed_origin.port
            except ValueError as error:
                raise ValueError(
                    "Production CORS_ORIGINS must contain explicit HTTPS origins"
                ) from error

        if self.database_url.casefold().startswith("sqlite"):
            raise ValueError("Production requires a PostgreSQL DATABASE_URL")


settings = Settings()
