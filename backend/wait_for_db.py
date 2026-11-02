"""Wait until DATABASE_URL stays reachable.

Postgres' official image accepts connections from a temporary server during
init, then restarts. One successful probe is not enough: require two probes
a few seconds apart so the API does not migrate against the server that is
about to exit.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings

STABLE_SUCCESSES = 2
PAUSE_SECONDS = 3
MAX_ATTEMPTS = 40


async def _probe(url: str) -> None:
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"timeout": 5},
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


async def wait_for_db() -> None:
    url = Settings().DATABASE_URL
    streak = 0
    last = "no attempt"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await _probe(url)
        except Exception as exc:
            streak = 0
            last = type(exc).__name__
            print(
                f"[wait-for-db] not ready (attempt {attempt}): {last}",
                flush=True,
            )
            await asyncio.sleep(2)
            continue
        streak += 1
        print(f"[wait-for-db] reachable ({streak}/{STABLE_SUCCESSES})", flush=True)
        if streak >= STABLE_SUCCESSES:
            return
        await asyncio.sleep(PAUSE_SECONDS)
    print(f"[wait-for-db] giving up after {MAX_ATTEMPTS} attempts ({last})", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(wait_for_db())
