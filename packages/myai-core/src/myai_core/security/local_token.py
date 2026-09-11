"""Per-installation local API token.

The local API is bound to loopback, but "same machine" is not "same user" and does not
protect against other local processes or a hostile web page performing cross-site
requests to ``127.0.0.1``. Every request therefore carries a bearer token that only the
user's own MyAI processes can read (owner-only file permissions).

The token is a 256-bit random value generated with :mod:`secrets`. It is never logged and
never embedded in frontend source; the desktop shell reads it from disk at runtime.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

TOKEN_BYTES = 32


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def load_or_create_token(token_file: Path) -> str:
    """Return the installation token, creating it atomically on first run."""
    existing = _read_token(token_file)
    if existing:
        return existing

    token = generate_token()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = token_file.with_suffix(".tmp")
    # O_EXCL avoids clobbering a token written concurrently by another instance.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(token)
        tmp.replace(token_file)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)

    # A concurrent writer may have won the os.replace race; re-read to converge.
    return _read_token(token_file) or token


def _read_token(token_file: Path) -> str | None:
    try:
        value = token_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def tokens_match(presented: str | None, expected: str) -> bool:
    """Constant-time comparison; ``None`` never matches."""
    if presented is None:
        return False
    return secrets.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))
