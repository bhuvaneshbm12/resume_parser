import os
import logging
from collections.abc import AsyncGenerator
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from dotenv import load_dotenv
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from models import metadata


load_dotenv()

logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.Pool | None = None


def get_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return DATABASE_URL


def mask_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if parsed.password is None:
        return database_url

    netloc = ""
    if parsed.username:
        netloc = f"{parsed.username}:***@"

    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc += hostname

    if parsed.port:
        netloc += f":{parsed.port}"

    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


async def connect_db() -> None:
    global pool
    if pool is None:
        database_url = get_database_url()
        try:
            pool = await asyncpg.create_pool(
                dsn=database_url,
                min_size=2,
                max_size=10,
            )
        except Exception:
            logger.critical(
                "Database pool initialization failed database_url=%s",
                mask_database_url(database_url),
                exc_info=True,
            )
            raise SystemExit(1)


async def check_database_connection() -> None:
    database_url = get_database_url()
    try:
        db_pool = await get_pool()
        async with db_pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
    except Exception:
        logger.critical(
            "Database startup check failed database_url=%s",
            mask_database_url(database_url),
            exc_info=True,
        )
        raise SystemExit(1)


async def close_db() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def get_pool() -> asyncpg.Pool:
    if pool is None:
        await connect_db()
    if pool is None:
        raise RuntimeError("Database pool was not initialized")
    return pool


async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    db_pool = await get_pool()
    async with db_pool.acquire() as connection:
        yield connection


async def init_db() -> None:
    db_pool = await get_pool()
    dialect = postgresql.dialect()
    async with db_pool.acquire() as connection:
        for table in metadata.sorted_tables:
            ddl = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect))
            await connection.execute(ddl)

        await connection.execute(
            """
            ALTER TABLE resumes
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """
        )

        for column_name in (
            "phone",
            "location",
            "linkedin",
            "github",
            "summary",
            "target_role",
            "years_experience",
            "ats_keyword_match_score",
            "experience_level",
            "domain_classification",
        ):
            await connection.execute(
                f"""
                ALTER TABLE parsed_fields
                ADD COLUMN IF NOT EXISTS {column_name} TEXT NOT NULL DEFAULT ''
                """
            )

        for column_name in (
            "projects",
            "certifications",
            "awards",
            "languages",
            "identity",
            "education_history",
            "skills_grouped",
            "positions_of_responsibility",
            "extracurriculars",
            "missing_fields",
            "contact_card",
            "role_timeline",
            "parser_flags",
        ):
            await connection.execute(
                f"""
                ALTER TABLE parsed_fields
                ADD COLUMN IF NOT EXISTS {column_name} JSONB NOT NULL DEFAULT '[]'::jsonb
                """
            )
