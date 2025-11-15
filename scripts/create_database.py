from __future__ import annotations

import argparse
import asyncio

import asyncpg
from rich.console import Console
from sqlalchemy.engine import URL
from sqlalchemy.engine.url import make_url

console = Console()


async def create_database_if_needed(dsn: str) -> None:
    url = make_url(dsn)
    database = url.database
    if not database:
        raise ValueError("DATABASE_URL must include a database name")

    admin_url = URL.create(
        drivername=url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database="postgres",
    )

    conn = await asyncpg.connect(
        user=admin_url.username,
        password=admin_url.password,
        host=admin_url.host,
        port=admin_url.port,
        database=admin_url.database,
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", database)
        if exists:
            console.print(f"[yellow]Database '{database}' already exists[/yellow]")
            return
        await conn.execute(f'CREATE DATABASE "{database}"')
        console.print(f"[green]Created database '{database}'[/green]")
    finally:
        await conn.close()


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ensure the Orbital Log database exists")
    parser.add_argument(
        "--dsn",
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/orbitallog",
        help="SQLAlchemy-style DATABASE_URL",
    )
    args = parser.parse_args(argv)
    asyncio.run(create_database_if_needed(args.dsn))


if __name__ == "__main__":
    cli()
