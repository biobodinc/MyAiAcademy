"""Per-client credentials for the local API (spec §47, §51-§53).

What this is, and what it is not
--------------------------------

The service listens on 127.0.0.1 only, so nothing on the network can reach it. These
credentials are therefore not about network access: they are about *which programs on this
machine may act as your AI*. The desktop app, the CLI and any third-party tool each hold
their own credential, so one grant can be revoked without disturbing the others, and every
recorded action can say which client performed it.

The installation token (``security/local_token``) remains the owner's credential: it is
readable only by the user's own account, it is what the desktop shell reads at start-up,
and it is what issues pairing codes. A pairing code is how a client that should *not* read
that file — the CLI, a tool the user is trying out — obtains a credential of its own.

Secrets at rest
---------------

Only the SHA-256 of a credential or a pairing code is stored. A secret is returned exactly
once, when it is created. That means a stolen copy of the database contains no working key,
and it means a lost credential is replaced rather than recovered, which is the honest
trade and is stated wherever a credential is issued.
"""

from __future__ import annotations

import hashlib
import platform
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ulid import ULID

from myai_core.audit.service import AuditCategory, AuditService
from myai_core.db.models import Device, PairingCode
from myai_core.schemas import ApiModel
from myai_core.security.capabilities import DEFAULT_GRANT, FULL_GRANT, Capability
from myai_core.security.capabilities import parse as parse_capabilities

TOKEN_BYTES = 32
CODE_DIGITS = 8
CODE_TTL = timedelta(minutes=5)
MAX_CODE_ATTEMPTS = 5
"""A code is burned after this many wrong guesses, so guessing is bounded and visible."""
OWNER_DEVICE_ID = "owner"
"""Reserved id for the installation token: the user's own processes, not a paired client."""

DEVICE_KINDS = ("desktop", "cli", "mobile", "integration", "unknown")


class DeviceRead(ApiModel):
    id: str
    name: str
    kind: str
    platform: str | None
    created_at: datetime
    last_seen_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str | None
    capabilities: list[str] = Field(
        default_factory=list, description="What this client may do. Empty means nothing."
    )

    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )

    @property
    def active(self) -> bool:
        return self.revoked_at is None


class IssuedCredential(ApiModel):
    """A credential, returned once. It is not stored and cannot be shown again."""

    device: DeviceRead
    token: str = Field(description="Shown once. Store it; it cannot be recovered.")
    note: str = "This credential is shown once. If it is lost, revoke the client and pair again."


class PairingCodeRead(ApiModel):
    """A pairing code, returned once, with the moment it stops working."""

    code: str
    label: str
    expires_at: datetime
    expires_in_seconds: int
    capabilities: list[str] = Field(
        default_factory=list, description="What the client that redeems this will be allowed to do."
    )
    note: str = (
        "Single use, and only until it expires. Type it into the client you are pairing; "
        "anyone who has it can obtain a credential, so treat it like a password."
    )


class PairingError(ValueError):
    """A code was wrong, expired, already used, or tried too many times."""


@dataclass(frozen=True, slots=True)
class Caller:
    """Who made a request: the owner's own processes, or a paired client."""

    device_id: str
    name: str
    is_owner: bool
    capabilities: frozenset[Capability] = frozenset()
    """What this client may do. Meaningless for the owner, who is not scoped."""

    def may(self, capability: Capability) -> bool:
        """The owner may do anything a client may. A client may do what it was granted."""
        return self.is_owner or capability in self.capabilities


OWNER_CALLER = Caller(
    device_id=OWNER_DEVICE_ID,
    name="This installation",
    is_owner=True,
    capabilities=FULL_GRANT,
)


def hash_secret(secret: str) -> str:
    """SHA-256 of a high-entropy secret.

    A password needs a slow KDF because it is guessable; these are 256-bit random values
    and 8-digit codes whose guessing is bounded by expiry and an attempt counter, so a
    plain digest is the right tool and a slow one would only cost every request.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def generate_code() -> str:
    """A numeric code the user can read out loud, from a cryptographic source."""
    return "".join(str(secrets.randbelow(10)) for _ in range(CODE_DIGITS))


def default_device_name(kind: str) -> str:
    host = platform.node() or "this machine"
    return f"{kind.title()} on {host}"


class DeviceService:
    """Issues, lists, resolves and revokes client credentials."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- listing ----------------------------------------------------------------------------

    def list_devices(self, *, include_revoked: bool = True) -> list[Device]:
        stmt = select(Device).order_by(Device.created_at.desc())
        if not include_revoked:
            stmt = stmt.where(Device.revoked_at.is_(None))
        return list(self._session.scalars(stmt).all())

    def active_count(self) -> int:
        return len(self.list_devices(include_revoked=False))

    def get(self, device_id: str) -> Device | None:
        return self._session.get(Device, device_id)

    # --- issuing ----------------------------------------------------------------------------

    def register(
        self,
        *,
        name: str,
        kind: str = "unknown",
        platform_name: str | None = None,
        actor: str | None = None,
        capabilities: frozenset[Capability] | None = None,
    ) -> tuple[Device, str]:
        """Create a client and return it with its one-time credential."""
        if kind not in DEVICE_KINDS:
            raise ValueError(f"Unknown client kind '{kind}'. One of: {', '.join(DEVICE_KINDS)}.")
        granted = DEFAULT_GRANT if capabilities is None else capabilities
        token = generate_token()
        device = Device(
            id=f"dev_{ULID()}",
            name=name.strip()[:120] or default_device_name(kind),
            kind=kind,
            platform=platform_name or platform.platform(),
            token_hash=hash_secret(token),
            capabilities=sorted(c.value for c in granted),
        )
        self._session.add(device)
        self._session.flush()
        AuditService(self._session).record(
            AuditCategory.SECURITY,
            "device_authorised",
            f"{device.name} was authorised to act as your AI",
            {
                "device_id": device.id,
                "kind": device.kind,
                # Recorded at the moment of the grant: what was approved has to be
                # answerable later, not inferred from what the row says today.
                "capabilities": sorted(c.value for c in granted),
            },
            device_id=actor,
        )
        return device, token

    # --- pairing ----------------------------------------------------------------------------

    def create_pairing_code(
        self,
        *,
        label: str = "",
        actor: str | None = None,
        capabilities: frozenset[Capability] | None = None,
    ) -> PairingCodeRead:
        """Create a code carrying the grant the owner approved.

        The grant is fixed here, not asked for by the client redeeming it. A program that
        could name its own permissions would make the consent meaningless.
        """
        granted = DEFAULT_GRANT if capabilities is None else capabilities
        code = generate_code()
        expires_at = datetime.now(tz=UTC) + CODE_TTL
        self._session.add(
            PairingCode(
                code_hash=hash_secret(code),
                label=label.strip()[:120],
                expires_at=expires_at,
                capabilities=sorted(c.value for c in granted),
            )
        )
        self._session.flush()
        AuditService(self._session).record(
            AuditCategory.SECURITY,
            "pairing_code_created",
            "A pairing code was created" + (f" for {label}" if label else ""),
            {
                "expires_at": expires_at.isoformat(),
                "ttl_seconds": int(CODE_TTL.total_seconds()),
                "capabilities": sorted(c.value for c in granted),
            },
            device_id=actor,
        )
        return PairingCodeRead(
            code=code,
            label=label,
            expires_at=expires_at,
            expires_in_seconds=int(CODE_TTL.total_seconds()),
            capabilities=sorted(c.value for c in granted),
        )

    def redeem_pairing_code(
        self, code: str, *, name: str, kind: str = "unknown", platform_name: str | None = None
    ) -> tuple[Device, str]:
        """Exchange a valid code for a credential. Raises :class:`PairingError` otherwise.

        A wrong code is counted against every live code rather than silently ignored: that
        is what makes guessing visible, and it is why a code dies after a few attempts.
        """
        now = datetime.now(tz=UTC)
        row = self._session.scalar(
            select(PairingCode).where(PairingCode.code_hash == hash_secret(code))
        )
        if row is None:
            self._count_failure()
            raise PairingError("That pairing code is not valid.")
        if row.used_at is not None:
            raise PairingError("That pairing code has already been used. Create another.")
        if _aware(row.expires_at) <= now:
            raise PairingError("That pairing code has expired. Create another.")
        if row.attempts >= MAX_CODE_ATTEMPTS:
            raise PairingError("That pairing code was tried too many times. Create another.")

        device, token = self.register(
            name=name,
            kind=kind,
            platform_name=platform_name,
            # Whatever the owner approved when they made the code, and nothing more.
            capabilities=parse_capabilities(row.capabilities),
        )
        row.used_at = now
        row.device_id = device.id
        self._session.flush()
        return device, token

    def _count_failure(self) -> None:
        """Charge a failed attempt to every code that is still live.

        Written in its own transaction on purpose. A rejected attempt raises, the request
        that raised it is rolled back, and a counter rolled back with it would count
        nothing — leaving guessing unbounded while appearing to be bounded.
        """
        now = datetime.now(tz=UTC)
        with Session(bind=self._session.get_bind()) as side:
            live = side.scalars(select(PairingCode).where(PairingCode.used_at.is_(None))).all()
            touched = 0
            for row in live:
                if _aware(row.expires_at) > now:
                    row.attempts += 1
                    touched += 1
            if touched:
                AuditService(side).record(
                    AuditCategory.SECURITY,
                    "pairing_code_rejected",
                    "A pairing attempt used a code that does not exist",
                    {"live_codes_charged": touched, "max_attempts": MAX_CODE_ATTEMPTS},
                )
            side.commit()

    # --- resolving and revoking ----------------------------------------------------------------

    def resolve(self, token: str) -> Device | None:
        """Find the active client holding this credential, and record that it was seen."""
        device = self._session.scalar(select(Device).where(Device.token_hash == hash_secret(token)))
        if device is None or device.revoked_at is not None:
            return None
        device.last_seen_at = datetime.now(tz=UTC)
        return device

    def revoke(self, device_id: str, *, reason: str = "", actor: str | None = None) -> Device:
        device = self._session.get(Device, device_id)
        if device is None:
            raise ValueError(f"Unknown client '{device_id}'.")
        if device.revoked_at is None:
            device.revoked_at = datetime.now(tz=UTC)
            device.revoked_reason = reason.strip() or "Revoked by you."
            device.version += 1
            self._session.flush()
            AuditService(self._session).record(
                AuditCategory.SECURITY,
                "device_revoked",
                f"{device.name} can no longer act as your AI",
                {"device_id": device.id, "reason": device.revoked_reason},
                device_id=actor,
            )
        return device


def _aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat stored times as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
