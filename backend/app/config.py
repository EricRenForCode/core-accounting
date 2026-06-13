"""Application configuration via pydantic-settings.

Reads from environment variables / .env file.
"""

from typing import List
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://accounting:accounting@localhost:5432/core_accounting",
        description="Primary async database URL (asyncpg driver)",
    )
    AI_READONLY_DATABASE_URL: str = Field(
        default="postgresql+asyncpg://accounting_ro:readonly@localhost:5432/core_accounting",
        description="Read-only database URL for AI queries (SELECT only)",
    )

    DB_POOL_SIZE: int = Field(default=20, description="Connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=10, description="Max overflow connections")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Pool timeout seconds")
    DB_POOL_RECYCLE: int = Field(default=3600, description="Connection recycle seconds")

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    # ── JWT Auth ──────────────────────────────────────────────
    JWT_SECRET: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_A_STRONG_SECRET",
        description="Secret key for JWT signing",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=120, description="Access token lifetime in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7, description="Refresh token lifetime in days"
    )

    # ── OpenAI / LLM ──────────────────────────────────────────
    OPENAI_API_KEY: SecretStr = Field(
        default=SecretStr("sk-CHANGE_ME"),
        description="OpenAI API key (used via langchain-openai)",
    )
    AI_MODEL: str = Field(
        default="gpt-4o", description="Default AI model identifier"
    )
    AI_FALLBACK_MODEL: str = Field(
        default="gpt-4o-mini", description="Fallback model if primary fails"
    )

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # ── Rate Limiting ─────────────────────────────────────────
    RATE_LIMIT_GLOBAL: str = Field(default="60/minute", description="Global rate limit")
    RATE_LIMIT_AI: str = Field(default="10/minute", description="AI endpoints rate limit")
    RATE_LIMIT_AUTH: str = Field(default="5/minute", description="Auth endpoints rate limit")

    # ── Application ───────────────────────────────────────────
    APP_NAME: str = Field(default="Core Accounting", description="Application name")
    APP_VERSION: str = Field(default="0.1.0", description="Application version")
    DEBUG: bool = Field(default=False, description="Debug mode")

    # ── System User ───────────────────────────────────────────
    SYSTEM_USER_ID: str = Field(
        default="00000000-0000-0000-0000-000000000000",
        description="System user UUID for automated operations (carry-forward, etc.)",
    )
