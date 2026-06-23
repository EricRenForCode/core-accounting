"""AI Period Checker — pre-close checks on an accounting period (§3.8)."""

from app.schemas.period import AIProceedCheckResponse


async def run_period_checks(period_id, db) -> AIProceedCheckResponse:
    """Run 10 standard pre-close checks on an accounting period.

    Delegates to the existing carry-forward/check endpoint logic.
    """
    if db is None:
        raise ValueError("db session is required")

    # Delegate to the check function in periods.py
    from app.api.v1.periods import check_period_before_close

    return await check_period_before_close(
        period_id=period_id,
        db=db,
    )
