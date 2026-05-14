import asyncio
import os
import socket

import asyncpg
from dotenv import load_dotenv


async def print_table(connection: asyncpg.Connection, table_name: str) -> None:
    rows = await connection.fetch(f"SELECT * FROM {table_name}")

    print(f"\n{table_name}")
    print("-" * len(table_name))
    if not rows:
        print("(no rows)")
        return

    for row in rows:
        print(dict(row))


async def main() -> None:
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    try:
        connection = await asyncpg.connect(dsn=database_url)
    except socket.gaierror:
        if "@postgres:" not in database_url:
            raise
        local_database_url = database_url.replace("@postgres:", "@localhost:", 1)
        print("Could not resolve host 'postgres'; retrying with localhost.")
        connection = await asyncpg.connect(dsn=local_database_url)

    try:
        await print_table(connection, "resumes")
        await print_table(connection, "parsed_fields")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
