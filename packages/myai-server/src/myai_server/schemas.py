"""What the account API accepts and returns.

The response models exist partly to shape the JSON and partly as a guard: a hand-built dict
picks up whatever the ORM object happens to carry, and the day someone adds a column named
`password_hash` next to `email` is the day that matters. Every response here is built from an
explicit field list, so a new column is invisible until somebody deliberately exposes it.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, EmailStr, Field

if TYPE_CHECKING:
    from myai_server.models import Account, Device

# Long enough that guessing is hopeless, short enough that nobody reaches for a sticky note.
# Length is the only rule: NIST SP 800-63B dropped composition requirements years ago because
# they push people towards "Passw0rd!" and little else.
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128


class ApiModel(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


Password = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


# --- requests -------------------------------------------------------------------------------


class SignUpRequest(ApiModel):
    email: EmailStr
    password: str = Password


class SignInRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class ChangePasswordRequest(ApiModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Password


class VerifyEmailRequest(ApiModel):
    token: str = Field(min_length=1, max_length=512)


class RedeemPairingRequest(ApiModel):
    code: str = Field(min_length=8, max_length=8, pattern=r"^\d{8}$")
    device_id: str = Field(min_length=1, max_length=255)
    device_name: str = Field(default="", max_length=255)


class RenameDeviceRequest(ApiModel):
    device_name: str = Field(min_length=1, max_length=255)


# --- responses ------------------------------------------------------------------------------


class AccountRead(ApiModel):
    account_id: str
    email: str | None
    email_verified: bool
    oauth_provider: str | None
    created_at: datetime


class DeviceRead(ApiModel):
    device_id: str
    device_name: str
    last_seen: datetime | None
    created_at: datetime
    revoked: bool


class AuthResult(ApiModel):
    """A session token, handed over once. It is stored only as a hash, so this is the only
    time it can be read."""

    token: str
    account: AccountRead


class SignUpResult(AuthResult):
    """A new account, signed in, plus the truth about the verification email.

    `verification_email_sent` is False when no provider is configured. The token itself is
    never returned — it is in the server log for local development, and putting it in an HTTP
    response would mean a misconfigured production server handing out working verification
    links to anyone who could reach the sign-up endpoint.
    """

    verification_email_sent: bool
    detail: str


class PairingCodeRead(ApiModel):
    code: str
    expires_at: datetime
    expires_in_seconds: int
    note: str = (
        "Enter this on the device you are adding, or scan the QR code. It works once and "
        "expires in a few minutes. Anyone who has it could add a device to your account, so "
        "do not share it."
    )


class AuditEventRead(ApiModel):
    event_type: str
    device_id: str | None
    ip_address: str | None
    created_at: datetime
    details: str | None


class Message(ApiModel):
    detail: str


def account_read(account: Account) -> AccountRead:
    return AccountRead(
        account_id=account.account_id,
        email=account.email,
        email_verified=account.email_verified_at is not None,
        oauth_provider=account.oauth_provider,
        created_at=account.created_at,
    )


def device_read(device: Device) -> DeviceRead:
    return DeviceRead(
        device_id=device.device_id,
        device_name=device.device_name,
        last_seen=device.last_seen,
        created_at=device.created_at,
        revoked=device.revoked_at is not None,
    )
