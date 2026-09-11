"""Stable AI identity identifiers.

``myai_<ULID>``: sortable, 26 characters of Crockford base32, no personal information.
"""

from __future__ import annotations

import re

from ulid import ULID

AI_ID_PREFIX = "myai_"
_AI_ID_RE = re.compile(r"^myai_[0-9A-HJKMNP-TV-Z]{26}$")


def new_ai_id() -> str:
    return f"{AI_ID_PREFIX}{ULID()}"


def is_valid_ai_id(value: str) -> bool:
    return bool(_AI_ID_RE.match(value))
