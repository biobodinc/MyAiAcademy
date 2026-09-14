"""Storing a password so that a stolen database is not a stolen account.

The threat here is offline guessing: someone takes the `accounts` table and grinds through
candidate passwords on their own hardware, as fast as they can buy. The only defence is to
make each individual guess expensive, so Argon2id — the same choice the portable package
makes in `myai_core.portable.crypto`, and for the same reason.

**The parameters are deliberately lighter than the package's.** That module spends 256 MiB
and says so: a package is unlocked once in a while and a full second is fine. A sign-in is
not that. Every sign-in pays this cost on the server, so the memory cost here is 64 MiB —
the second configuration RFC 9106 recommends — which is still far beyond what a GPU array
parallelises cheaply, while leaving the server able to answer more than one person at a time.

**The cost is recorded next to the hash, not assumed.** Hashes are written in the standard
PHC string format, so raising these constants later does not lock out everyone who signed up
before: their stored parameters keep verifying, and `needs_rehash` says whose hash should be
upgraded the next time they prove they know the password.
"""

from __future__ import annotations

import base64
import hmac
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

HASH_BYTES = 32
SALT_BYTES = 16

# RFC 9106's second recommended option, sized for a login rather than for a rare unlock.
DEFAULT_MEMORY_KIB = 64 * 1024  # 64 MiB
DEFAULT_ITERATIONS = 3
DEFAULT_LANES = 4

# Verifying a wrong password must cost the same as verifying a right one even when there is
# no account at all, or the response time alone tells an attacker which emails are registered.
_DUMMY_PASSWORD = "not a real password, only a way to spend the same time"  # noqa: S105


@dataclass(frozen=True, slots=True)
class HashParams:
    memory_kib: int = DEFAULT_MEMORY_KIB
    iterations: int = DEFAULT_ITERATIONS
    lanes: int = DEFAULT_LANES


def hash_password(password: str, params: HashParams | None = None) -> str:
    """Hash a password into a self-describing PHC string."""
    if not password:
        raise ValueError("A password is required.")
    params = params or HashParams()
    salt = os.urandom(SALT_BYTES)
    digest = _derive(password, salt, params)
    return (
        f"$argon2id$v=19$m={params.memory_kib},t={params.iterations},p={params.lanes}"
        f"${_b64(salt)}${_b64(digest)}"
    )


def verify_password(password: str, encoded: str | None) -> bool:
    """Check a password against a stored hash, in constant time.

    A missing or unreadable hash still spends the work of a real verification. Accounts
    created through OAuth have no password, and returning early for those would let someone
    tell an OAuth account from a password account by watching the clock.
    """
    try:
        params, salt, expected = _decode(encoded or "")
    except ValueError:
        _derive(_DUMMY_PASSWORD, b"\x00" * SALT_BYTES, HashParams())
        return False
    if not password:
        return False
    return hmac.compare_digest(_derive(password, salt, params), expected)


def needs_rehash(encoded: str | None) -> bool:
    """Whether a stored hash was made with weaker parameters than we now use."""
    try:
        params, _, _ = _decode(encoded or "")
    except ValueError:
        return True
    return (
        params.memory_kib < DEFAULT_MEMORY_KIB
        or params.iterations < DEFAULT_ITERATIONS
        or params.lanes < DEFAULT_LANES
    )


def _derive(password: str, salt: bytes, params: HashParams) -> bytes:
    return Argon2id(
        salt=salt,
        length=HASH_BYTES,
        iterations=params.iterations,
        lanes=params.lanes,
        memory_cost=params.memory_kib,
    ).derive(password.encode("utf-8"))


def _decode(encoded: str) -> tuple[HashParams, bytes, bytes]:
    parts = encoded.split("$")
    # A PHC string starts with an empty field: "$argon2id$v=19$m=..,t=..,p=..$salt$hash".
    if len(parts) != 6 or parts[0] != "" or parts[1] != "argon2id":
        raise ValueError("Not an argon2id hash this version can read.")
    costs = dict(item.split("=", 1) for item in parts[3].split(","))
    try:
        params = HashParams(
            memory_kib=int(costs["m"]), iterations=int(costs["t"]), lanes=int(costs["p"])
        )
        return params, _unb64(parts[4]), _unb64(parts[5])
    except (KeyError, ValueError) as exc:
        raise ValueError("Unreadable argon2id parameters.") from exc


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text, validate=True)
