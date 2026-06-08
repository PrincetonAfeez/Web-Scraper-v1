"""Response safety helpers."""

from __future__ import annotations


def is_allowed_content_type(content_type: str, allowed: tuple[str, ...]) -> bool:
    # Deny a missing/blank Content-Type: an undeclared body should not be
    # decoded as HTML. Servers that serve real pages set this header.
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in allowed
