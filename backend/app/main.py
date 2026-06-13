"""Core Accounting — FastAPI application entry point.

Startup sequence:
 1. Load configuration from environment / .env
 2. Configure async database engines (primary + ai_readonly)
 3. Install SQLAlchemy audit event listeners
 4. Register CORS middleware from config origins
 5. Register CorrelationID middleware
 6. Register AuditContext middleware
 7. Register API v1 router under /api/v1
 8. Register exception handlers (errors.py)
 9. Health check at /health

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import Settings
from app.core.audit import install_audit_listeners
from app.core.database import configure as configure_db
from app.core.database import dispose as dispose_db
from app.core.errors import register_exception_handlers
from app.core.middleware import AuditContextMiddleware, CorrelationIDMiddleware

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — configure engines on startup, dispose on shutdown."""
    configure_db(settings)
    install_audit_listeners()
    yield
    await dispose_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise-grade core accounting system backend",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

# ── Correlation ID Middleware ─────────────────────────────────
app.add_middleware(CorrelationIDMiddleware)

# ── Audit Context Middleware ──────────────────────────────────
app.add_middleware(AuditContextMiddleware)

# ── API Routes ────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")

# ── Exception Handlers ────────────────────────────────────────
register_exception_handlers(app)


# ── Root Redirect ─────────────────────────────────────────────
@app.get("/")
async def root() -> dict:
    """Root endpoint — redirects to API docs."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
