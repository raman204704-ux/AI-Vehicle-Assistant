import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.database.connection import engine
from app.routers import (
    analytics,
    assistant,
    auth,
    document,
    maintenance,
    mechanic,
    reminders,
    service_history,
    vehicle,
)

logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _log_event(level: int, event: str, **fields: object) -> None:
    logger.log(
        level,
        json.dumps(
            {"event": event, **fields},
            ensure_ascii=True,
            separators=(",", ":"),
        ),
    )


def _database_is_ready() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        _log_event(
            logging.WARNING,
            "readiness_check_failed",
            dependency="database",
            error_type=type(error).__name__,
        )
        return False
    return True


def _redis_is_ready() -> bool:
    client = None
    try:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
    except (RedisError, ValueError) as error:
        _log_event(
            logging.WARNING,
            "readiness_check_failed",
            dependency="redis",
            error_type=type(error).__name__,
        )
        return False
    finally:
        if client is not None:
            client.close()
    return True


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    settings.validate_runtime_configuration()
    yield


app = FastAPI(
    title="AI Vehicle Maintenance Assistant",
    description="AI-powered vehicle maintenance management platform",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else str(uuid.uuid4())
    )
    request.state.request_id = request_id
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    _log_event(
        logging.INFO,
        "http_request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    errors = error.errors()
    _log_event(
        logging.INFO,
        "request_validation_failed",
        request_id=getattr(request.state, "request_id", ""),
        error_count=len(errors),
    )
    safe_details = [
        {
            "loc": list(item.get("loc", ())),
            "type": item.get("type", "validation_error"),
        }
        for item in errors
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": safe_details},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    _log_event(
        logging.ERROR,
        "unhandled_request_error",
        request_id=getattr(request.state, "request_id", ""),
        error_type=type(error).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(vehicle.router)
app.include_router(document.router)
app.include_router(document.download_router)
app.include_router(service_history.router)
app.include_router(maintenance.router)
app.include_router(analytics.router)
app.include_router(assistant.router)
app.include_router(mechanic.router)
app.include_router(reminders.router)


@app.get("/")
def home():
    return {
        "message": "AI Vehicle Maintenance Assistant API",
        "status": "Running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/ready")
def readiness_check():
    checks = {
        "database": _database_is_ready(),
        "redis": _redis_is_ready(),
    }
    ready = all(status for status in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": {
                name: "ok" if status else "unavailable"
                for name, status in checks.items()
            },
        },
    )