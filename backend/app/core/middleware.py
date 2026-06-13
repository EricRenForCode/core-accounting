"""Middleware stack (§4).

- CorrelationIDMiddleware: Injects X-Correlation-ID header (generates UUID if missing).
- AuditContextMiddleware: Sets/clears audit context for SQLAlchemy events.

Request flow:
  Request → CORS → CorrelationID → AuditContext → Router → Service → DB
"""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.audit import clear_audit_context, set_audit_context


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware that ensures every request has an X-Correlation-ID.

    If the client sends the header, its value is preserved.
    If absent, a new UUID (v4) is generated.

    The correlation ID is attached to the request state and included in
    the response header for traceability across services.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request state for logging and audit
        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)

        # Echo back in response header
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class AuditContextMiddleware(BaseHTTPMiddleware):
    """Middleware that sets the audit context (user ID, request) before each request.

    The audit module uses thread-local storage to provide user/request context
    to the SQLAlchemy event listeners. This middleware bridges the gap between
    FastAPI's async request context and the synchronous after_flush event.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Try to extract user from request state (set by auth middleware)
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", None) if user else None
        set_audit_context(user_id=user_id, request=request)

        try:
            response = await call_next(request)
            return response
        finally:
            clear_audit_context()
