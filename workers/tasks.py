import asyncio
import json
import logging
import os
import uuid

import asyncpg
import httpx
from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from schemas import ParsedResume


load_dotenv()

logger = logging.getLogger(__name__)
celery_app = Celery("resume_parser")
celery_app.config_from_object("workers.celery_config")

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = (
    "You are a resume parser. Extract structured data from the resume text provided. "
    "Return ONLY valid JSON with no explanation, no markdown, no backticks."
)

class GeminiRateLimitError(Exception):
    pass


class GeminiAPITimeoutError(Exception):
    pass


class gemini:
    RateLimitError = GeminiRateLimitError
    APITimeoutError = GeminiAPITimeoutError


USER_PROMPT = (
    "Extract the following fields from this resume: name (string), email (string), "
    "skills (array of strings), experience (array of objects with keys: company, "
    "role, duration), education (array of objects with keys: institution, degree, year). "
    "If a string field is missing, use an empty string. If an array field is missing, "
    "use an empty array. Return only JSON."
)


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return DATABASE_URL


def require_gemini_api_key() -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    return GEMINI_API_KEY


def strip_json_code_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 2 or not lines[-1].strip().startswith("```"):
        return stripped

    return "\n".join(lines[1:-1]).strip()


def normalize_resume_payload(payload: dict) -> dict:
    for key in ("name", "email"):
        if payload.get(key) is None:
            payload[key] = ""

    for key in ("skills", "experience", "education"):
        if payload.get(key) is None:
            payload[key] = []

    return payload


def parse_with_gemini(raw_text: str) -> dict:
    client = genai.Client(api_key=require_gemini_api_key())
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"{USER_PROMPT}\n\nResume text:\n{raw_text}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=SYSTEM_PROMPT,
            ),
        )
    except genai_errors.ClientError as exc:
        if getattr(exc, "code", None) == 429 or getattr(exc, "status_code", None) == 429:
            raise gemini.RateLimitError(str(exc)) from exc
        raise
    except (httpx.TimeoutException, TimeoutError) as exc:
        raise gemini.APITimeoutError(str(exc)) from exc

    content = response.text
    if not content:
        raise ValueError("Gemini returned an empty response")

    return normalize_resume_payload(json.loads(strip_json_code_fence(content)))


def is_retryable_llm_error(exc: Exception) -> bool:
    if isinstance(exc, (gemini.RateLimitError, gemini.APITimeoutError, genai_errors.ServerError)):
        return True
    return False


async def set_resume_status(
    connection: asyncpg.Connection,
    resume_id: uuid.UUID,
    status: str,
) -> None:
    await connection.execute(
        "UPDATE resumes SET status = $1, updated_at = NOW() WHERE id = $2",
        status,
        resume_id,
    )


async def mark_resume_failed(resume_id: uuid.UUID, error_message: str) -> None:
    connection = await asyncpg.connect(dsn=require_database_url())
    try:
        await set_resume_status(connection, resume_id, "failed")
        logger.error(
            "Resume parsing task failed for resume_id=%s error=%s",
            resume_id,
            error_message,
        )
    finally:
        await connection.close()


async def run_parse_resume(resume_id: uuid.UUID, retry_count: int = 0) -> None:
    logger.info("Starting resume parsing task resume_id=%s retry=%s", resume_id, retry_count)
    connection = await asyncpg.connect(dsn=require_database_url())
    try:
        row = await connection.fetchrow(
            "SELECT raw_text FROM resumes WHERE id = $1",
            resume_id,
        )
        if row is None:
            raise ValueError(f"Resume {resume_id} was not found")

        await set_resume_status(connection, resume_id, "processing")

        try:
            payload = parse_with_gemini(row["raw_text"])
        except Exception as exc:
            if is_retryable_llm_error(exc):
                logger.warning(
                    "Retryable LLM failure for resume_id=%s retry=%s error=%s",
                    resume_id,
                    retry_count,
                    exc,
                )
                raise
            raise

        try:
            parsed = ParsedResume.model_validate(payload)
        except ValidationError:
            await set_resume_status(connection, resume_id, "failed")
            logger.exception("Gemini response validation failed for resume_id=%s", resume_id)
            return

        await connection.execute(
            """
            INSERT INTO parsed_fields (
                id,
                resume_id,
                name,
                email,
                skills,
                experience,
                education
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb)
            """,
            uuid.uuid4(),
            resume_id,
            parsed.name,
            parsed.email,
            json.dumps(parsed.skills),
            json.dumps(parsed.experience),
            json.dumps(parsed.education),
        )
        await set_resume_status(connection, resume_id, "done")
        logger.info("Completed resume parsing task resume_id=%s", resume_id)
    except Exception as exc:
        if is_retryable_llm_error(exc):
            if retry_count < 3:
                logger.warning(
                    "Retrying resume parsing task resume_id=%s retry=%s error=%s",
                    resume_id,
                    retry_count + 1,
                    exc,
                )
                raise
            await set_resume_status(connection, resume_id, "failed")
            logger.exception("Resume parsing task failed after retries resume_id=%s", resume_id)
            raise

        await set_resume_status(connection, resume_id, "failed")
        logger.exception("Resume parsing task failed for resume_id=%s", resume_id)
        raise
    finally:
        await connection.close()


@celery_app.task(
    bind=True,
    name="workers.tasks.parse_resume_task",
    autoretry_for=(gemini.RateLimitError, gemini.APITimeoutError),
    max_retries=3,
    retry_backoff=10,
    soft_time_limit=60,
    time_limit=70,
)
def parse_resume_task(self, resume_id: str) -> None:
    parsed_resume_id = uuid.UUID(resume_id)
    try:
        asyncio.run(run_parse_resume(parsed_resume_id, self.request.retries))
    except SoftTimeLimitExceeded:
        asyncio.run(mark_resume_failed(parsed_resume_id, "timeout"))
        raise
