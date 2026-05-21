from contextlib import asynccontextmanager
from datetime import UTC, datetime
import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from database import check_database_connection, close_db, connect_db, get_pool, init_db
from logging_config import configure_logging
from routers.parse import router as parse_router


configure_logging()
logger = logging.getLogger(__name__)
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
PORT = int(os.environ.get("PORT", 8000))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            logger.info(
                "%s %s status=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await check_database_connection()
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Resume Parser API", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(parse_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal server error", "detail": str(exc)},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/metrics")
async def metrics() -> dict[str, int | float]:
    db_pool = await get_pool()
    async with db_pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            SELECT
                COUNT(*)::int AS total_resumes,
                COUNT(*) FILTER (WHERE status = 'done')::int AS completed,
                COUNT(*) FILTER (WHERE status = 'failed')::int AS failed,
                COUNT(*) FILTER (WHERE status IN ('pending', 'processing'))::int AS pending,
                COALESCE(
                    AVG(EXTRACT(EPOCH FROM updated_at - created_at))
                        FILTER (WHERE status = 'done'),
                    0
                )::float AS average_parse_time_seconds
            FROM resumes
            """
        )

    return {
        "total_resumes": row["total_resumes"],
        "completed": row["completed"],
        "failed": row["failed"],
        "pending": row["pending"],
        "average_parse_time_seconds": row["average_parse_time_seconds"],
    }
