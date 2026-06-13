"""Common Pydantic schemas — pagination, errors, success messages."""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated list response (§3.1)."""

    items: list[T] = Field(default_factory=list)
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    pages: int = Field(..., description="Total number of pages")


class ErrorDetail(BaseModel):
    """Error detail object for standard error responses (§3.1)."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    detail: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ErrorResponse(BaseModel):
    """Standard error response envelope (§3.1)."""

    error: ErrorDetail


class SuccessMessage(BaseModel):
    """Simple success response."""

    message: str = Field(default="ok")
    data: Optional[dict[str, Any]] = Field(default=None)


class HealthResponse(BaseModel):
    """Health check response (§3.14)."""

    status: str
    version: str
    db: str  # "ok" | "error"
    redis: str  # "ok" | "error"
