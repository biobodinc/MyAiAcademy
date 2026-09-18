"""Signing up, signing in, and the settings that belong to the account itself."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from myai_server import email as email_module
from myai_server.deps import AccountDep, ServiceDep, SessionAuthDep, StateDep
from myai_server.schemas import (
    AccountRead,
    AuditEventRead,
    AuthResult,
    ChangePasswordRequest,
    Message,
    SignInRequest,
    SignUpRequest,
    SignUpResult,
    VerifyEmailRequest,
    account_read,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])

# Sign-in failures say this and nothing more. Which half was wrong is exactly what someone
# working through a list of addresses wants to know.
_REFUSED = "That email and password do not match an account."


@router.post("/sign-up", response_model=SignUpResult, status_code=status.HTTP_201_CREATED)
def sign_up(body: SignUpRequest, service: ServiceDep, state: StateDep) -> SignUpResult:
    """Create an account and send the address a link to prove it.

    An address already in use is answered plainly, with 409. That does tell an attacker the
    address is registered — but the alternative is a sign-up form that appears to succeed and
    then silently does nothing, and someone who cannot register their own address and is not
    told why will assume the product is broken. Sign-in, where the leak would actually be
    worth something, gives nothing away.
    """
    address = body.email.strip().lower()
    if service.get_account_by_email(address) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An account already uses that email address. Sign in instead, or use another address.",
        )

    account, verification_token = service.sign_up(address, body.password)
    email_module.send_verification(
        state.email,
        to=address,
        base_url=state.settings.base_url,
        token=verification_token,
    )
    token = service.create_session(account.account_id)
    sent = state.email.configured
    return SignUpResult(
        token=token,
        account=account_read(account),
        verification_email_sent=sent,
        detail=(
            "Check your email for a link to confirm the address."
            if sent
            else "No email provider is configured on this server, so the confirmation link "
            "was written to the server log instead of being sent."
        ),
    )


@router.post("/sign-in", response_model=AuthResult)
def sign_in(body: SignInRequest, service: ServiceDep) -> AuthResult:
    result = service.sign_in(body.email, body.password)
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _REFUSED)
    account, token = result
    return AuthResult(token=token, account=account_read(account))


@router.post("/sign-out", response_model=Message)
def sign_out(auth: SessionAuthDep, service: ServiceDep) -> Message:
    service.revoke_session_row(auth)
    return Message(detail="Signed out.")


@router.get("/me", response_model=AccountRead)
def read_me(account: AccountDep) -> AccountRead:
    return account_read(account)


@router.post("/verify-email", response_model=AccountRead)
def verify_email(body: VerifyEmailRequest, service: ServiceDep) -> AccountRead:
    """Redeem the link from the sign-up email. No session needed: following a link from an
    email client is the normal way this happens, and that request carries no token."""
    account = service.verify_email(body.token)
    if account is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That confirmation link has already been used, or it has expired. Ask for a new "
            "one from your account settings.",
        )
    return account_read(account)


@router.post("/resend-verification", response_model=Message)
def resend_verification(account: AccountDep, service: ServiceDep, state: StateDep) -> Message:
    if account.email is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This account has no email address to confirm."
        )
    if account.email_verified_at is not None:
        return Message(detail="That address is already confirmed.")

    token = service.create_email_verification(account.account_id, account.email)
    email_module.send_verification(
        state.email, to=account.email, base_url=state.settings.base_url, token=token
    )
    return Message(
        detail=(
            "Sent. Check your email for the link."
            if state.email.configured
            else "No email provider is configured on this server, so the link was written to "
            "the server log instead of being sent."
        )
    )


@router.post("/change-password", response_model=AuthResult)
def change_password(
    body: ChangePasswordRequest, account: AccountDep, service: ServiceDep
) -> AuthResult:
    """Replace the password. Every existing session ends, including this one.

    A new token comes back so whoever is at the keyboard stays signed in. Anyone else holding
    a session for this account does not — which is the point of changing a password.
    """
    if not service.change_password(account.account_id, body.current_password, body.new_password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That is not the current password.")
    token = service.create_session(account.account_id)
    return AuthResult(token=token, account=account_read(account))


@router.get("/activity", response_model=list[AuditEventRead])
def read_activity(
    account: AccountDep, service: ServiceDep, limit: int = 100
) -> list[AuditEventRead]:
    """Everything this account has done, newest first."""
    limit = max(1, min(limit, 500))
    return [
        AuditEventRead(
            event_type=event.event_type,
            device_id=event.device_id,
            ip_address=event.ip_address,
            created_at=event.created_at,
            details=event.details,
        )
        for event in service.list_audit_events(account.account_id, limit=limit)
    ]
