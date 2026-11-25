"""Helpers for workload analytics, pseudonymization and safe tabular exports."""

import hashlib
import hmac
from typing import Any

from app.core.config import PSEUDONYM_SECRET


def pseudo(teacher_id: str) -> str:
    """Return a stable non-reversible teacher key for analytics and exports."""

    return hmac.new(
        PSEUDONYM_SECRET.encode(), teacher_id.encode(), hashlib.sha256
    ).hexdigest()[:24]


def safe_cell(value: Any) -> Any:
    """Prefix formula-like text so spreadsheet applications treat it as data."""

    if isinstance(value, str) and value.lstrip("\x00\t\r\n ").startswith(
        ("=", "+", "-", "@")
    ):
        return "'" + value
    return value
