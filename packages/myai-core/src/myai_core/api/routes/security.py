"""Security Center (spec §47, §51-§53, §61): who may act as your AI, and how it is stored.

Two privilege levels exist here, and the difference matters. The **owner** is whoever can
read the installation token file — the user's own account on this machine. Only the owner
may issue a credential, create a pairing code or revoke a client. A **paired client** may
use the AI and read this page, but cannot hand out access or take it away; otherwise one
compromised client could quietly grant itself a spare key.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from myai_core.api.deps import SessionDep, StateDep
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
        account=AccountState(),
        notes=[
            "The local API is bound to 127.0.0.1, so nothing on your network can reach it. "
            "Pairing a client grants access to programs on this machine, not to other "
            "machines; that arrives with the mobile app.",
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
