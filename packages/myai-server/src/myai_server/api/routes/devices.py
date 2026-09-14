"""The devices on an account, and the codes that add one.

Two privilege levels, as in `myai_core`'s Security Center. A signed-in person may list, add
and revoke their own devices. A device being paired has no credential yet, so `/devices/pair`
is the one route here that cannot require one — the code itself is the authentication.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from myai_server.deps import AccountDep, ServiceDep
from myai_server.schemas import (
    AuthResult,
    DeviceRead,
    Message,
    PairingCodeRead,
    RedeemPairingRequest,
    RenameDeviceRequest,
    account_read,
    device_read,
)
from myai_server.services import PAIRING_CODE_MINUTES

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceRead])
def list_devices(account: AccountDep, service: ServiceDep) -> list[DeviceRead]:
    return [device_read(d) for d in service.list_devices(account.account_id)]


@router.post("/pairing-codes", response_model=PairingCodeRead, status_code=status.HTTP_201_CREATED)
def create_pairing_code(account: AccountDep, service: ServiceDep) -> PairingCodeRead:
    """Make a single-use code for adding a device. Shown once, expires in minutes."""
    row = service.issue_pairing_code(account.account_id)
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    return PairingCodeRead(
        code=row.code,
        expires_at=expires_at,
        expires_in_seconds=max(0, math.floor((expires_at - datetime.now(UTC)).total_seconds())),
    )


@router.patch("/{device_id}", response_model=DeviceRead)
def rename_device(
    device_id: str, body: RenameDeviceRequest, account: AccountDep, service: ServiceDep
) -> DeviceRead:
    device = service.rename_device(account.account_id, device_id, body.device_name.strip())
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such device on this account.")
    return device_read(device)


@router.post("/{device_id}/revoke", response_model=DeviceRead)
def revoke_device(device_id: str, account: AccountDep, service: ServiceDep) -> DeviceRead:
    """Cut a device off. Its sessions end immediately, not whenever they would have expired."""
    device = service.revoke_device(account.account_id, device_id)
    if device is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No such device on this account, or it is already revoked.",
        )
    return device_read(device)


# --- the one unauthenticated route ------------------------------------------------------------

pairing_router = APIRouter(prefix="/devices", tags=["devices"])


@pairing_router.post("/pair", response_model=AuthResult, status_code=status.HTTP_201_CREATED)
def pair(body: RedeemPairingRequest, service: ServiceDep) -> AuthResult:
    """Exchange a pairing code for this device's own session.

    Every way this can fail answers the same way. A code that is wrong, spent, expired or
    burned through its attempts are four different states, and telling them apart would hand a
    guesser a way to tell "close" from "nowhere near".
    """
    result = service.redeem_pairing_code(body.code, body.device_id, body.device_name.strip())
    if result is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "That code does not work. It may have been used already or expired — codes last "
            f"about {PAIRING_CODE_MINUTES} minutes. Generate a new one and try again.",
        )
    device, token = result
    account = service.get_account(device.account_id)
    if account is None:  # pragma: no cover - the device's account was just read
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That code does not work.")
    return AuthResult(token=token, account=account_read(account))


@pairing_router.get("/pair", response_model=Message, include_in_schema=False)
def pair_help() -> Message:
    return Message(detail="POST a pairing code here to add this device to an account.")
