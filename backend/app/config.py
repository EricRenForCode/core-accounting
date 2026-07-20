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
        extra="ignore",
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
        default=1, description="Refresh token lifetime in days (daily re-login)"
    )

    # ── DeepSeek / LLM ────────────────────────────────────────
    DEEPSEEK_API_KEY: SecretStr = Field(
        default=SecretStr("sk-CHANGE_ME"),
        description="DeepSeek API key (OpenAI-compatible API)",
    )
    DEEPSEEK_MODEL: str = Field(
        default="deepseek-chat", description="Default DeepSeek model identifier"
    )
    DEEPSEEK_FALLBACK_MODEL: str = Field(
        default="deepseek-chat", description="Fallback DeepSeek model if primary fails"
    )

    # ── Aliyun OCR (票据识别) ─────────────────────────────────
    ALIYUN_OCR_ACCESS_KEY_ID: SecretStr = Field(
        default=SecretStr(""),
        description="Aliyun AccessKey ID for OCR API (视觉智能开放平台/OCR). "
        "Leave empty to disable — recognition falls back to the rule engine.",
    )
    ALIYUN_OCR_ACCESS_KEY_SECRET: SecretStr = Field(
        default=SecretStr(""), description="Aliyun AccessKey Secret for OCR API"
    )
    ALIYUN_OCR_ENDPOINT: str = Field(
        default="ocr-api.cn-hangzhou.aliyuncs.com",
        description="Aliyun OCR API endpoint",
    )

    @property
    def aliyun_ocr_configured(self) -> bool:
        return bool(
            self.ALIYUN_OCR_ACCESS_KEY_ID.get_secret_value().strip()
            and self.ALIYUN_OCR_ACCESS_KEY_SECRET.get_secret_value().strip()
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
    DEBUG: bool = Field(default=False, description="Debug mode (SQLAlchemy echo)")
    ENVIRONMENT: str = Field(
        default="development",
        description="Deployment environment: 'development' or 'production'. "
        "Production enables strict startup config validation.",
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    # ── File Uploads ──────────────────────────────────────────
    UPLOAD_DIR: str = Field(
        default="uploads",
        description="Base directory for uploaded files (original documents, etc.)",
    )
    UPLOAD_MAX_BYTES: int = Field(
        default=20 * 1024 * 1024,
        description="Maximum upload file size in bytes (default 20 MB)",
    )

    # ── System User ───────────────────────────────────────────
    SYSTEM_USER_ID: str = Field(
        default="00000000-0000-0000-0000-000000000000",
        description="System user UUID for automated operations (carry-forward, etc.)",
    )

    # ── Production validation ─────────────────────────────────
    _INSECURE_JWT_SECRET = "CHANGE_ME_IN_PRODUCTION_USE_A_STRONG_SECRET"

    def production_issues(self) -> list[str]:
        """Return a list of critical misconfigurations for production.

        Only meaningful when ENVIRONMENT=production. A non-empty list means the
        app should refuse to start (see startup validation in main.py).
        """
        issues: list[str] = []

        if (
            self.JWT_SECRET == self._INSECURE_JWT_SECRET
            or len(self.JWT_SECRET) < 32
        ):
            issues.append(
                "JWT_SECRET is the default or too short (<32 chars). "
                "Generate a strong one: openssl rand -hex 32"
            )

        if "CHANGE_ME" in self.DATABASE_URL:
            issues.append("DATABASE_URL still contains a placeholder password (CHANGE_ME).")

        if any("localhost" in o or "127.0.0.1" in o for o in self.CORS_ORIGINS):
            issues.append(
                "CORS_ORIGINS contains localhost — set your real frontend origin(s) in production."
            )

        return issues

    def production_warnings(self) -> list[str]:
        """Return non-fatal production warnings (logged, do not block startup)."""
        warnings: list[str] = []
        if self.DEEPSEEK_API_KEY.get_secret_value().endswith("CHANGE_ME"):
            warnings.append(
                "DEEPSEEK_API_KEY is a placeholder — AI features will be unavailable."
            )
        if not self.aliyun_ocr_configured:
            warnings.append(
                "ALIYUN_OCR_ACCESS_KEY_ID/SECRET not set — 票据识别 will use the "
                "rule-based fallback instead of real OCR."
            )
        return warnings
