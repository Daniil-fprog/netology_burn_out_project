"""Shared SQLAlchemy helpers for domain models.

The project stores UUID values as strings to keep the same model definitions
portable between SQLite in development and PostgreSQL in production.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime


def new_uuid() -> str:
    """Return a database-independent UUID string."""

    return str(uuid4())


def utcnow() -> datetime:
    """Return an aware UTC timestamp for SQLAlchemy defaults."""

    return datetime.now(timezone.utc)


class TimestampMixin:
    """Add creation and last-update timestamps to a model."""

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
