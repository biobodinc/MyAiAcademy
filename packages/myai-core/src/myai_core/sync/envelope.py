"""Encrypting a batch so that only the other device can read it (spec §18, §55).

Why this exists before the relay does
-------------------------------------

Two devices on the same network already have a private channel: the pinned TLS connection
from Phase 6. This adds nothing there, and does not pretend to.

It exists for the case the spec describes next — reaching your computer from somewhere else,
through a relay. A relay is a machine in the middle that both devices can reach. Whoever
runs it can see everything that passes through unless the traffic is already unreadable when
it arrives. TLS to the relay does not help: the relay terminates it.

So the payload is encrypted between the two devices, with a key the relay never sees, and
the relay carries ciphertext it cannot open. Building it now, and proving it with a test
that puts a relay in the middle and shows what it gets, means the relay can be added later
without anyone having to re-litigate whether it can be trusted. It cannot, and it does not
need to be.

The key
-------

Both devices derive it with HKDF-SHA256 from the secret they already share — the credential
issued at pairing — with a salt and an info string that name this use. Deriving rather than
reusing means the credential still authenticates and only the derived key decrypts, so
neither job can be mistaken for the other later.

AES-256-GCM provides confidentiality and integrity together: a batch altered in transit
fails to decrypt rather than arriving subtly wrong. The nonce is random per message and sent
alongside; the twelve bytes GCM expects are not enough for a counter to be safe across
devices that cannot coordinate, but they are ample for random generation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

NONCE_BYTES = 12
KEY_BYTES = 32
SALT = b"myai-academy/sync/v1"
INFO = b"device-to-device sync payload"


class CannotOpenError(Exception):
    """The payload was not written for us, or was changed on the way."""


def derive_key(shared_secret: str) -> bytes:
    """The symmetric key two paired devices both arrive at, and nothing else does."""
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=SALT, info=INFO).derive(
        shared_secret.encode("utf-8")
    )


@dataclass(frozen=True, slots=True)
class Envelope:
    """What actually crosses the wire. Only ``nonce`` and ``ciphertext`` carry anything."""

    nonce: bytes
    ciphertext: bytes

    def to_json(self) -> dict[str, str]:
        import base64

        return {
            "nonce": base64.b64encode(self.nonce).decode("ascii"),
            "payload": base64.b64encode(self.ciphertext).decode("ascii"),
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Envelope:
        import base64

        try:
            return cls(
                nonce=base64.b64decode(str(raw["nonce"]), validate=True),
                ciphertext=base64.b64decode(str(raw["payload"]), validate=True),
            )
        except (KeyError, ValueError) as exc:
            raise CannotOpenError("That is not a sync envelope.") from exc


def seal(key: bytes, body: dict[str, Any]) -> Envelope:
    nonce = os.urandom(NONCE_BYTES)
    plaintext = json.dumps(body, separators=(",", ":"), default=str).encode("utf-8")
    return Envelope(nonce=nonce, ciphertext=AESGCM(key).encrypt(nonce, plaintext, None))


def open_envelope(key: bytes, envelope: Envelope) -> dict[str, Any]:
    try:
        plaintext = AESGCM(key).decrypt(envelope.nonce, envelope.ciphertext, None)
    except (InvalidTag, ValueError) as exc:
        raise CannotOpenError(
            "This message was not written for this device, or was changed on the way."
        ) from exc
    body = json.loads(plaintext.decode("utf-8"))
    if not isinstance(body, dict):
        raise CannotOpenError("That envelope did not contain a sync batch.")
    return body
