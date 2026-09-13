"""Locking a portable package with a password (spec §25, §27).

A `.myai` package is meant to be carried on a USB stick or left on a backup drive, which
means assuming it will be found by someone it was not meant for. Encryption is optional
because a package kept on the machine that made it gains little from it, but when it is
turned on it has to be the real thing rather than a gesture.

The two choices that matter
---------------------------

**Argon2id for the key.** A password is short and human, so the only defence against someone
grinding through guesses offline is to make each guess expensive in *memory* as well as time.
Argon2id is the current answer and won the Password Hashing Competition for this case; PBKDF2
and even scrypt at ordinary settings are far cheaper to attack with a GPU. The parameters are
recorded in the package so that a file written today still opens when the defaults are raised
later.

**AES-256-GCM for the contents, with the path bound in.** GCM authenticates as well as
encrypts, so a package altered on the drive fails to open rather than opening subtly wrong.
Binding the entry's path as associated data means a file cannot be swapped for another from
the same package — `identity/profile.json` will not decrypt in the place of
`memory/memories.json`, even though both were sealed with the same key.

The password is never written anywhere, and the derived key is never stored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

KEY_BYTES = 32
SALT_BYTES = 16
NONCE_BYTES = 12

# Argon2id parameters. These are the interactive-use settings from the RFC 9106 guidance,
# raised in memory because a package is unlocked rarely and a second of work is acceptable
# where a login would not tolerate it.
DEFAULT_MEMORY_KIB = 256 * 1024  # 256 MiB
DEFAULT_ITERATIONS = 3
DEFAULT_LANES = 4


class WrongPasswordError(Exception):
    """The password did not open the package, or the package was altered."""


@dataclass(frozen=True, slots=True)
class KdfParams:
    """How the key was derived. Written into the package so old files keep opening."""

    algorithm: str = "argon2id"
    salt: bytes = b""
    memory_kib: int = DEFAULT_MEMORY_KIB
    iterations: int = DEFAULT_ITERATIONS
    lanes: int = DEFAULT_LANES

    def to_json(self) -> dict[str, Any]:
        import base64

        return {
            "algorithm": self.algorithm,
            "salt": base64.b64encode(self.salt).decode("ascii"),
            "memory_kib": self.memory_kib,
            "iterations": self.iterations,
            "lanes": self.lanes,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> KdfParams:
        import base64

        algorithm = str(raw.get("algorithm", ""))
        if algorithm != "argon2id":
            raise WrongPasswordError(
                f"This package was locked with {algorithm or 'an unknown method'}, which this "
                "version cannot open. Update MyAI Academy and try again."
            )
        try:
            salt = base64.b64decode(str(raw["salt"]), validate=True)
            return cls(
                algorithm=algorithm,
                salt=salt,
                memory_kib=int(raw["memory_kib"]),
                iterations=int(raw["iterations"]),
                lanes=int(raw["lanes"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WrongPasswordError("This package does not say how it was locked.") from exc


def new_params() -> KdfParams:
    return KdfParams(salt=os.urandom(SALT_BYTES))


def derive_key(password: str, params: KdfParams) -> bytes:
    """Turn a password into a key. Deliberately slow, and deliberately memory-hungry."""
    if not password:
        raise WrongPasswordError("A locked package needs a password.")
    return Argon2id(
        salt=params.salt,
        length=KEY_BYTES,
        iterations=params.iterations,
        lanes=params.lanes,
        memory_cost=params.memory_kib,
    ).derive(password.encode("utf-8"))


def seal(key: bytes, path: str, plaintext: bytes) -> bytes:
    """Encrypt one entry. The nonce is prepended; the path is authenticated, not encrypted."""
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, path.encode("utf-8"))


def unseal(key: bytes, path: str, payload: bytes) -> bytes:
    """Decrypt one entry, refusing anything altered or moved to a different path."""
    if len(payload) <= NONCE_BYTES:
        raise WrongPasswordError(f"{path} is too short to be a locked file.")
    nonce, body = payload[:NONCE_BYTES], payload[NONCE_BYTES:]
    try:
        return AESGCM(key).decrypt(nonce, body, path.encode("utf-8"))
    except (InvalidTag, ValueError) as exc:
        raise WrongPasswordError(
            "That password did not open this package, or the file has been changed since it "
            "was made."
        ) from exc
