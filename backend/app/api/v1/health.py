"""Health check endpoint (§3.14)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.database import get_db
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """Check application health: DB connectivity, Redis, version.

    Returns 200 with status breakdown or 503 if a critical dependency is down.
    """
    settings = Settings()

    # Check DB
    db_status = "error"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    # Check Redis (lazy — returns ok if import succeeds)
    redis_status = "error"
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.close()
        redis_status = "ok"
    except Exception:
        redis_status = "error"

    overall = "ok" if db_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        db=db_status,
        redis=redis_status,
    )
