# ── Multi-stage Dockerfile for Core Accounting Backend ──

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies for psycopg2 / asyncpg compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install the same runtime set CI uses (uv.lock), not the older requirements.txt pins.
# langchain-deepseek currently requires pydantic>=2.7.4, and OCR/Excel imports are
# declared on the project rather than in requirements.txt.
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv venv /opt/venv && \
    UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    uv sync --frozen --no-dev --no-install-project

# ── Stage 2: Production runtime ───────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY . .

# Create non-root user. uploads/ is created first so a named volume
# mounted there inherits the app user on first use.
RUN useradd --create-home --shell /bin/bash app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://127.0.0.1:8000/api/v1/health').raise_for_status()" || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
