import os
from collections.abc import AsyncGenerator

import asyncpg
from dotenv import load_dotenv
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from models import metadata


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.Pool | None = None


def get_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return DATABASE_URL


async def connect_db() -> None:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(dsn=get_database_url())


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
