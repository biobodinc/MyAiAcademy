"""Security Center (spec §47, §51-§53, §61): who may act as your AI, and how it is stored.

Two privilege levels exist here, and the difference matters. The **owner** is whoever can
read the installation token file — the user's own account on this machine. Only the owner
may issue a credential, create a pairing code or revoke a client. A **paired client** may
use the AI and read this page, but cannot hand out access or take it away; otherwise one
compromised client could quietly grant itself a spare key.
"""

from __future__ import annotations

import json
import socket
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import Field

from myai_core.api.deps import SessionDep, StateDep
from myai_core.audit.service import AuditCategory, AuditService
from myai_core.network import start_listener
from myai_core.schemas import ApiModel
from myai_core.security.auth import CallerDep, LocalOrigin
from myai_core.security.devices import (
    DEVICE_KINDS,
    Caller,
    DeviceRead,
    DeviceService,
    IssuedCredential,
    PairingCodeRead,
    PairingError,
)
from myai_core.security.host_certificate import HostCertificate, load_or_create, local_addresses
from myai_core.security.storage_checks import SecretStorageReport, check_secret_storage

router = APIRouter(prefix="/security", tags=["security"])


class AccountState(ApiModel):
    """The account picture, stated as it is rather than as it is planned to be."""

    linked: bool = False
    available: bool = False
    provider: str | None = None
    detail: str = (
        "This build has no accounts. There is no sign-in, no account server and no code "
        "path that would send your data anywhere. An account is planned as the way to get "
        "installers and to sign in on more than one device; until it exists, everything "
        "here is local to this machine."
    )


class NetworkAccess(ApiModel):
    """Whether devices on this network may reach the service, and how they verify it."""

    enabled: bool
    host: str | None = None
    port: int | None = None
    addresses: list[str] = Field(
        default_factory=list, description="Where a device on this network can reach you."
    )
    certificate_fingerprint: str | None = Field(
        default=None, description="SHA-256 of the certificate a device pins when pairing."
    )
    certificate_fingerprint_groups: str | None = Field(
        default=None, description="The same fingerprint in readable groups, to compare by eye."
    )
    public_key_pin: str | None = Field(
        default=None,
        description=(
            "The public key pin in the form every pinning library uses, 'sha256/<base64>'. "
            "The fingerprint above identifies the certificate; this identifies the key inside "
            "it, which is what Android's and iOS's pinning APIs actually check."
        ),
    )
    certificate_expires_at: datetime | None = None
    detail: str


class PairingInvite(ApiModel):
    """Everything a device needs to reach this host safely, for one pairing.

    The fingerprint and the code travel together, over the air gap of the user looking at
    their own screen. That is what lets the device pin this host's certificate and refuse
    every other, with no certificate authority in the trust path.
    """

    code: str
    expires_at: datetime
    expires_in_seconds: int
    host_name: str
    addresses: list[str]
    port: int
    certificate_fingerprint: str
    certificate_fingerprint_groups: str
    public_key_pin: str
    payload: str = Field(description="Compact JSON for a QR code; the same fields, encoded.")
    note: str


class SecurityOverview(ApiModel):
    """What protects this installation right now."""

    bound_to_loopback: bool = Field(
        default=True, description="The service listens on 127.0.0.1 only; nothing on the LAN."
    )
    caller_name: str
    caller_is_owner: bool
    active_clients: int
    revoked_clients: int
    secret_storage: SecretStorageReport
    network: NetworkAccess
    account: AccountState
    notes: list[str]


class RegisterClient(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="integration", description=f"One of: {', '.join(DEVICE_KINDS)}")


class PairRequest(ApiModel):
    code: str = Field(min_length=4, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="cli")


class RevokeRequest(ApiModel):
    reason: str = Field(default="", max_length=500)


class PairingCodeRequest(ApiModel):
    label: str = Field(default="", max_length=120)


@router.get("", response_model=SecurityOverview)
def read_overview(state: StateDep, session: SessionDep, caller: CallerDep) -> SecurityOverview:
    devices = DeviceService(session)
    all_clients = devices.list_devices()
    active = [d for d in all_clients if d.revoked_at is None]
    return SecurityOverview(
        caller_name=caller.name,
        caller_is_owner=caller.is_owner,
        active_clients=len(active),
        revoked_clients=len(all_clients) - len(active),
        secret_storage=check_secret_storage(state.paths),
        network=describe_network(state),
        account=AccountState(),
        notes=[
            "The local API is bound to 127.0.0.1. Nothing on your network can reach it "
            "unless you turn on network access, which is off until you do and is recorded "
            "in the audit log both ways.",
            "Credentials are stored as SHA-256 hashes. A credential is shown once when it "
            "is issued and cannot be recovered afterwards, only replaced.",
            "Only this installation's own token may issue or revoke access. A paired "
            "client can use your AI but cannot hand out access.",
        ],
    )


@router.get("/devices", response_model=list[DeviceRead])
def list_devices(session: SessionDep, caller: CallerDep) -> list[DeviceRead]:
    return [DeviceRead.model_validate(d) for d in DeviceService(session).list_devices()]


@router.post("/devices", response_model=IssuedCredential, status_code=201)
def register_device(
    request: RegisterClient, session: SessionDep, caller: CallerDep
) -> IssuedCredential:
    """Issue a credential directly. Owner only; the secret is returned once."""
    _require_owner(caller)
    try:
        device, token = DeviceService(session).register(
            name=request.name, kind=request.kind, actor=caller.device_id
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return IssuedCredential(device=DeviceRead.model_validate(device), token=token)


@router.post("/devices/{device_id}/revoke", response_model=DeviceRead)
def revoke_device(
    device_id: str, request: RevokeRequest, session: SessionDep, caller: CallerDep
) -> DeviceRead:
    """Stop a client from acting as your AI. Takes effect on its next request."""
    _require_owner(caller)
    try:
        device = DeviceService(session).revoke(
            device_id, reason=request.reason, actor=caller.device_id
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return DeviceRead.model_validate(device)


@router.post("/pairing-codes", response_model=PairingCodeRead, status_code=201)
def create_pairing_code(
    request: PairingCodeRequest, session: SessionDep, caller: CallerDep
) -> PairingCodeRead:
    """Create a single-use code a client can exchange for its own credential. Owner only."""
    _require_owner(caller)
    return DeviceService(session).create_pairing_code(label=request.label, actor=caller.device_id)


@router.get("/account", response_model=AccountState)
def read_account(caller: CallerDep) -> AccountState:
    return AccountState()


class NetworkAccessRequest(ApiModel):
    enabled: bool
    port: int | None = Field(default=None, ge=1024, le=65535)


@router.post("/network", response_model=NetworkAccess)
def set_network_access(
    body: NetworkAccessRequest,
    request: Request,
    state: StateDep,
    session: SessionDep,
    caller: CallerDep,
) -> NetworkAccess:
    """Let paired devices on this network reach the service, or stop them. Owner only.

    Starting and stopping are both recorded: "can my AI be reached from the network" is
    exactly the kind of thing someone should be able to check after the fact.
    """
    _require_owner(caller)
    audit = AuditService(session, actor_device_id=caller.device_id)
    if not body.enabled:
        if state.network is not None:
            state.network.stop()
            state.network = None
            audit.record(
                AuditCategory.SECURITY,
                "network_access_disabled",
                "Devices on your network can no longer reach this AI",
            )
        return describe_network(state)

    if state.network is not None and state.network.running:
        return describe_network(state)

    settings = state.settings
    port = body.port or (settings.lan_port if settings else 41338)
    host = settings.lan_host if settings else "0.0.0.0"  # noqa: S104 - deliberately reachable
    certificate = _certificate(state)
    listener = start_listener(request.app, host=host, port=port, certificate=certificate)
    if not listener.running:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Could not listen on port {port}. Another program may be using it.",
        )
    state.network = listener
    audit.record(
        AuditCategory.SECURITY,
        "network_access_enabled",
        f"Devices you pair can now reach this AI at port {port} over HTTPS",
        {"port": port, "fingerprint": certificate.fingerprint_sha256},
    )
    return describe_network(state)


@router.post("/pairing-invite", response_model=PairingInvite)
def create_pairing_invite(
    body: PairingCodeRequest, state: StateDep, session: SessionDep, caller: CallerDep
) -> PairingInvite:
    """A pairing code together with how to reach this host and which certificate to trust."""
    _require_owner(caller)
    if state.network is None or not state.network.running:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Turn on network access first: a device cannot reach this machine until you do.",
        )
    certificate = state.network.certificate
    code = DeviceService(session).create_pairing_code(label=body.label, actor=caller.device_id)
    addresses = [a for a in local_addresses() if a != "127.0.0.1"] or local_addresses()
    payload = {
        "v": 1,
        "host": socket.gethostname() or "MyAI host",
        "addresses": addresses,
        "port": state.network.port,
        "fp": certificate.fingerprint_sha256,
        # The key pin as OkHttp and TrustKit spell it. A device needs this one to configure
        # a pinning library; the fingerprint above is the one a person compares on screen.
        "spki": certificate.public_key_pin,
        "code": code.code,
        "exp": code.expires_at.isoformat(),
    }
    return PairingInvite(
        code=code.code,
        expires_at=code.expires_at,
        expires_in_seconds=code.expires_in_seconds,
        host_name=str(payload["host"]),
        addresses=addresses,
        port=state.network.port,
        certificate_fingerprint=certificate.fingerprint_sha256,
        certificate_fingerprint_groups=certificate.fingerprint_groups,
        public_key_pin=certificate.public_key_pin,
        payload=json.dumps(payload, separators=(",", ":")),
        note=(
            "Scan this on the device you are pairing. It carries the certificate to trust as "
            "well as the code, so the device accepts only this machine. It works once and "
            "expires in a few minutes; anyone who sees it could pair, so show it to nobody else."
        ),
    )


def describe_network(state: StateDep) -> NetworkAccess:
    listener = state.network
    if listener is None or not listener.running:
        return NetworkAccess(
            enabled=False,
            detail=(
                "Off. The service listens on this machine only, so nothing on your network "
                "can reach it — including your own phone until you turn this on."
            ),
        )
    certificate = listener.certificate
    return NetworkAccess(
        enabled=True,
        host=listener.host,
        port=listener.port,
        addresses=local_addresses(),
        certificate_fingerprint=certificate.fingerprint_sha256,
        certificate_fingerprint_groups=certificate.fingerprint_groups,
        public_key_pin=certificate.public_key_pin,
        certificate_expires_at=certificate.not_after,
        detail=(
            "On. Devices you have paired can reach this AI over HTTPS on this network. They "
            "verify this machine by its certificate fingerprint, and this installation's own "
            "token is refused over the network — a device uses its own credential."
        ),
    )


def _certificate(state: StateDep) -> HostCertificate:
    return load_or_create(state.paths.data_dir)


def _require_owner(caller: Caller) -> None:
    if not caller.is_owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only this installation can grant or revoke access. Do this in the app on this "
            "machine, where the installation token is readable.",
        )


# --- the one unauthenticated route ------------------------------------------------------------

pairing_router = APIRouter(prefix="/security", tags=["security"], dependencies=[LocalOrigin])


@pairing_router.post("/pair", response_model=IssuedCredential, status_code=201)
def pair(request: PairRequest, session: SessionDep) -> IssuedCredential:
    """Exchange a pairing code for a credential of your own.

    This is the only route that cannot require a credential — a client has none yet — so
    the code itself is the authentication. It is still behind the loopback bind and the
    Host and Origin checks, it is single use, it expires in minutes, and a wrong code is
    counted against every live code so guessing is bounded and visible in the audit log.
    """
    try:
        device, token = DeviceService(session).redeem_pairing_code(
            request.code.strip(), name=request.name, kind=request.kind
        )
    except PairingError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return IssuedCredential(device=DeviceRead.model_validate(device), token=token)
