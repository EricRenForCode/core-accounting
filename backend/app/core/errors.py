"""Exception handlers for standardized error responses (§3.1, appendix A).

Registers handlers for:
- 400 VALIDATION_ERROR (Pydantic validation)
- 401 UNAUTHORIZED
- 403 INSUFFICIENT_PERMISSIONS / AI_READONLY_VIOLATION
- 404 VOUCHER_NOT_FOUND / ACCOUNT_NOT_FOUND / PERIOD_NOT_FOUND / TEMPLATE_NOT_FOUND
- 409 Business logic conflicts (VOUCHER_NOT_DRAFT, PERIOD_CLOSED, UNBALANCED_VOUCHER, etc.)
- 422 UNBALANCED_ENTRIES
- 429 RATE_LIMITED / AI_RATE_LIMITED
- 500 INTERNAL_ERROR
- 502 AI_GENERATION_FAILED / AI_INVALID_RESPONSE
- 503 SERVICE_UNAVAILABLE
"""

import traceback
from typing import Union

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorDetail, ErrorResponse


class AppException(Exception):
    """Base application exception with error code and HTTP status."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: dict | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail or {}


# ── Domain-Specific Exceptions ────────────────────────────────


class VoucherNotFoundError(AppException):
    def __init__(self, voucher_id: str | None = None):
        super().__init__(404, "VOUCHER_NOT_FOUND", "凭证不存在", {"voucher_id": voucher_id})


class AccountNotFoundError(AppException):
    def __init__(self, account_id: str | None = None):
        super().__init__(404, "ACCOUNT_NOT_FOUND", "科目不存在", {"account_id": account_id})


class PeriodNotFoundError(AppException):
    def __init__(self, period_id: str | None = None):
        super().__init__(404, "PERIOD_NOT_FOUND", "会计期间不存在", {"period_id": period_id})


class VoucherNotDraftError(AppException):
    def __init__(self):
        super().__init__(409, "VOUCHER_NOT_DRAFT", "凭证非草稿状态，不可编辑")


class VoucherAlreadyPostedError(AppException):
    def __init__(self):
        super().__init__(409, "VOUCHER_ALREADY_POSTED", "凭证已记账，不可重复操作")


class PeriodClosedError(AppException):
    def __init__(self):
        super().__init__(409, "PERIOD_CLOSED", "期间已结账，不可操作")


class PeriodAlreadyClosedError(AppException):
    def __init__(self):
        super().__init__(409, "PERIOD_ALREADY_CLOSED", "期间已结账，不可重复结账")


class UnbalancedVoucherError(AppException):
    def __init__(self, detail: dict | None = None):
        super().__init__(409, "UNBALANCED_VOUCHER", "凭证借贷不平衡", detail)


class AccountHasVouchersError(AppException):
    def __init__(self):
        super().__init__(409, "ACCOUNT_HAS_VOUCHERS", "科目存在凭证引用，不可删除")


class ReadOnlyViolationError(AppException):
    def __init__(self, stmt_type: str = ""):
        super().__init__(
            403,
            "AI_READONLY_VIOLATION",
            f"AI 查询仅允许 SELECT 语句，收到 {stmt_type}",
            {"statement_type": stmt_type},
        )


class AIGenerationFailedError(AppException):
    def __init__(self, detail: str = ""):
        super().__init__(502, "AI_GENERATION_FAILED", f"LLM 生成失败: {detail}")


class AIInvalidResponseError(AppException):
    def __init__(self, detail: str = ""):
        super().__init__(502, "AI_INVALID_RESPONSE", f"LLM 返回格式不符预期: {detail}")


# ── Exception Handlers ────────────────────────────────────────


def make_error_response(status_code: int, code: str, message: str, detail: dict | None = None) -> JSONResponse:
    """Build a standardized error JSONResponse."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=code, message=message, detail=detail or {})
        ).model_dump(),
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle domain-specific AppExceptions."""
    return make_error_response(exc.status_code, exc.code, exc.message, exc.detail)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard Starlette HTTP exceptions."""
    code_map = {
        401: "UNAUTHORIZED",
        403: "INSUFFICIENT_PERMISSIONS",
        404: "NOT_FOUND",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, "ERROR")
    return make_error_response(exc.status_code, code, str(exc.detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors with a standard format."""
    errors = exc.errors()
    detail_msgs = [
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
        for e in errors[:5]  # Max 5 errors in response
    ]
    return make_error_response(
        422,
        "VALIDATION_ERROR",
        "请求参数校验失败",
        {"errors": errors, "message": "; ".join(detail_msgs)},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — log traceback, return 500."""
    traceback.print_exc()
    return make_error_response(500, "INTERNAL_ERROR", "服务器内部错误")


def register_exception_handlers(app) -> None:
    """Register all exception handlers on a FastAPI application."""

    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
