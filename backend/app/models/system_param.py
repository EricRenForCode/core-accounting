"""System parameter model — key-value config store."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SystemParam(Base):
    """System-wide configuration parameters stored as key-value pairs.

    Used for company name, base currency, accounting standard, etc.
    """

    __tablename__ = "system_params"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    key: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="Parameter key"
    )
    value: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Parameter value"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SystemParam {self.key}={self.value[:30]}>"
