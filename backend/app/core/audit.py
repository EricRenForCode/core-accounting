"""Audit logging middleware via SQLAlchemy event listener (§4).

Listens for INSERT/UPDATE/DELETE on all tracked models and writes
corresponding entries to the audit_logs table.

Tracks: Voucher, VoucherEntry, Account, AccountBalance, Period, User, Role,
        FixedAsset, Department, Individual, Counterparty, Project.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.audit import AuditLog

# Models to track for auditing
TRACKED_MODELS: set[str] = {
    "vouchers",
    "voucher_entries",
    "accounts",
    "account_balances",
    "periods",
    "users",
    "roles",
    "fixed_assets",
    "departments",
    "individuals",
    "counterparties",
    "projects",
    "cash_journals",
    "bank_journals",
}

# Thread-local storage for current user and request context
_current_user_id: Optional[uuid.UUID] = None
_current_request: Optional[Request] = None


def set_audit_context(user_id: Optional[uuid.UUID], request: Optional[Request] = None) -> None:
    """Set the current user and request for audit logging.

    Called by middleware before each request.
    """
    global _current_user_id, _current_request
    _current_user_id = user_id
    _current_request = request


def clear_audit_context() -> None:
    """Clear audit context after request completes."""
    global _current_user_id, _current_request
    _current_user_id = None
    _current_request = None


def _get_client_ip() -> Optional[str]:
    """Extract client IP from the current request."""
    global _current_request
    if _current_request is None:
        return None
    # Try X-Forwarded-For header first
    forwarded = _current_request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # Fall back to direct client
    client = getattr(_current_request, "client", None)
    if client:
        return client.host
    return None


def _serialize_instance(instance: Any) -> dict[str, Any]:
    """Serialize a SQLAlchemy model instance to a dict for audit logging.

    Only includes non-relationship, non-internal attributes.
    """
    result: dict[str, Any] = {}
    for col in instance.__table__.columns:
        try:
            val = getattr(instance, col.name)
            # Convert UUID, datetime, Decimal to string for JSONB
            if isinstance(val, uuid.UUID):
                result[col.name] = str(val)
            elif isinstance(val, datetime):
                result[col.name] = val.isoformat()
            elif val is not None:
                result[col.name] = val
            else:
                result[col.name] = None
        except Exception:
            result[col.name] = None
    return result


def _write_audit_log(
    session: Session,
    action: str,
    instance: Any,
) -> None:
    """Write a single audit log entry for a model change."""
    table_name = instance.__tablename__
    if table_name not in TRACKED_MODELS:
        return

    new_values = _serialize_instance(instance)
    resource_id = new_values.get("id")

    audit_entry = AuditLog(
        user_id=_current_user_id,
        action=action,
        resource_type=table_name,
        resource_id=resource_id,
        new_values=new_values if action in ("INSERT", "UPDATE") else None,
        old_values=None,  # Can't easily get old values from after_flush without inspection
        ip_address=_get_client_ip(),
    )
    session.add(audit_entry)


def install_audit_listeners() -> None:
    """Register SQLAlchemy event listeners for audit logging.

    Called once at application startup to wire up after_flush events
    that capture INSERT, UPDATE, and DELETE operations.
    """

    def _after_flush(session: Session, flush_context: Any) -> None:
        """Callback after SQLAlchemy flush — intercepts all changes."""
        for instance in session.new:
            _write_audit_log(session, "INSERT", instance)

        for instance in session.dirty:
            _write_audit_log(session, "UPDATE", instance)

        for instance in session.deleted:
            _write_audit_log(session, "DELETE", instance)

    # Attach to the Session class
    event.listen(Session, "after_flush", _after_flush)
