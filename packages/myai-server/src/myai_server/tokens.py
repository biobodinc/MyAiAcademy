"""Secrets that identify a session or an email, and how they are kept.

Two rules, both of which exist so that reading the database is not the same as holding the
keys to every live account:

**Only the hash is stored.** A session token and an email-verification link are bearer
secrets — whoever holds one *is* the person, for as long as it lives. They are generated
here, returned once, and written to the database as SHA-256 of the token. A copy of the
`sessions` table is then a list of hashes, which cannot be presented to anything.

Plain SHA-256 is right here and wrong for passwords: these are 256 bits of output from a CSPRNG,
so there is no guessing to slow down. `passwords.py` uses Argon2id precisely because a human
password does not have that property.

**Comparison is constant-time and happens on the hash.** Lookup is by the hashed value, so a
timing difference in the database index leaks nothing about the token itself.
"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def new_token() -> tuple[str, str]:
    """Make a bearer token. Returns (token to hand out, hash to store)."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
