"""Create or update the AI read-only PostgreSQL role.

The production API container runs this after migrations. It connects with
DATABASE_URL (the Compose database owner) and applies DB_RO_USER /
DB_RO_PASSWORD / DB_NAME. The role can SELECT existing and future tables in
schema public and nothing else.
"""

from __future__ import annotations

import asyncio
import os
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def ident(value: str, label: str) -> str:
    """Return a safe unquoted SQL identifier or raise ValueError."""
    if not value or _IDENT.fullmatch(value) is None:
        raise ValueError(f"{label} must be a plain SQL identifier")
    return value


def sql_literal(value: str) -> str:
    """Quote a string for a SQL literal (standard_conforming_strings)."""
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("value must be a single line without NUL")
    return "'" + value.replace("'", "''") + "'"


async def ensure() -> None:
    user = ident(os.environ.get("DB_RO_USER", "accounting_ro"), "DB_RO_USER")
    db_name = ident(os.environ.get("DB_NAME", "core_accounting"), "DB_NAME")
    password = os.environ.get("DB_RO_PASSWORD", "")
    if not password or "CHANGE_ME" in password or len(password) < 16:
        raise SystemExit(
            "DB_RO_PASSWORD must be at least 16 characters and not a placeholder. "
            "Generate one with: openssl rand -hex 32"
        )

    password_sql = sql_literal(password)
    engine = create_async_engine(Settings().DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
                {"name": user},
            )
            if exists.scalar() is None:
                await conn.execute(
                    text(
                        f"CREATE ROLE {user} LOGIN PASSWORD {password_sql} "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE"
                    )
                )
            else:
                await conn.execute(
                    text(
                        f"ALTER ROLE {user} WITH LOGIN PASSWORD {password_sql} "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE"
                    )
                )
            await conn.execute(text(f"GRANT CONNECT ON DATABASE {db_name} TO {user}"))
            await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {user}"))
            await conn.execute(
                text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {user}")
            )
            await conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    f"GRANT SELECT ON TABLES TO {user}"
                )
            )
    finally:
        await engine.dispose()
    print(f"Read-only role ensured: {user}")


if __name__ == "__main__":
    asyncio.run(ensure())
