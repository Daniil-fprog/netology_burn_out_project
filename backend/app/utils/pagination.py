"""Helpers for paginated API responses."""

from typing import TypeVar


Item = TypeVar("Item")


def paginate(items: list[Item], page: int, page_size: int) -> dict:
    """Return one page of items in the common API response format."""
    start = (page - 1) * page_size
    return {
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "items": items[start : start + page_size],
    }
