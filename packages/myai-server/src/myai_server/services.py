"""Account management: what the routes are allowed to do, and what always gets recorded.

Every state change goes through here rather than through the routes, for two reasons. The
routes stay thin enough to read in one sitting, and — more importantly — the audit record is
written in the same place as the change it describes, so a new endpoint cannot add a way to
touch an account that leaves no trace.

Nothing in this module commits. The request boundary owns the transaction (see `deps.py`), so
a request that fails halfway leaves no half-made account behind.
"""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from myai_server import passwords, tokens
from myai_server.models import (
    Account,
    AuditEvent,
    Device,
    EmailVerification,
    PairingCode,
    Session,
)

WEB_SESSION_DAYS = 30
DEVICE_SESSION_DAYS = 365
EMAIL_VERIFICATION_HOURS = 24

# Wrong guesses a live pairing code tolerates before it stops working. Ten leaves room for
# someone mistyping a code off their own screen, and leaves an attacker needing to be lucky
# within ten tries out of a hundred million.
MAX_PAIRING_ATTEMPTS = 10

# Long enough to walk to the other device and type it, short enough that a code left on screen
# does not stay dangerous.
PAIRING_CODE_MINUTES = 10


def generate_account_id() -> str:
    """Generate a 16-digit random account ID."""
    return _digits(16)


def generate_pairing_code() -> str:
    """Generate an 8-digit pairing code."""
    return _digits(8)


def _digits(count: int) -> str:
    """`count` random digits, from the system CSPRNG rather than from `random`.

    `random` is a Mersenne Twister: watch 624 outputs and every future one is determined. A
    pairing code is worth a device on someone's account, and codes are shown to whoever asks
    for them, so predicting the next one has to be as hard as guessing it.
    """
    return "".join(secrets.choice(string.digits) for _ in range(count))


def _aware(value: datetime) -> datetime:
    """Read a timestamp back as UTC-aware.

    SQLite hands back naive datetimes even for columns declared `timezone=True`, so a value
    that round-trips through the database cannot be compared to `datetime.now(UTC)` without
    this. Postgres does preserve the offset; this is a no-op there.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class AccountService:
    """Account management service.

    Who is acting is supplied once, at construction, rather than passed to every call — the
    same shape `myai_core`'s `AuditService` uses, and for the same reason: a route that
    forgets to thread the caller through should not silently produce an anonymous audit entry.
    """

    def __init__(
        self,
        session: DbSession,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.session = session
        self.ip_address = ip_address
        self.user_agent = user_agent

    # --- accounts -----------------------------------------------------------------------

    def create_account(
        self,
        email: str | None = None,
        password_hash: str | None = None,
        oauth_provider: str | None = None,
        oauth_id: str | None = None,
    ) -> Account:
        """Create a new account."""
        account_id = generate_account_id()
        account = Account(
            account_id=account_id,
            email=email,
            password_hash=password_hash,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id,
        )
        self.session.add(account)
        self.session.flush()

        # Log account creation
        self._log_event(account_id, "sign_up")

        return account

    def sign_up(self, email: str, password: str) -> tuple[Account, str]:
        """Register with an address and a password.

        Returns the account and the verification token to put in the email. The account
        exists immediately but unverified: holding sign-up open until the link is followed
        would mean storing the password somewhere outside the accounts table, which is worse.
        """
        account = self.create_account(
            email=email.strip().lower(), password_hash=passwords.hash_password(password)
        )
        token = self.create_email_verification(account.account_id, account.email)
        return account, token

    def sign_in(self, email: str, password: str) -> tuple[Account, str] | None:
        """Check an address and password, and start a session if they are right.

        Returns None for both "no such account" and "wrong password", having spent the same
        work either way — the caller must not be able to tell which it was.
        """
        account = self.get_account_by_email(email.strip().lower())
        stored = account.password_hash if account else None
        if not passwords.verify_password(password, stored) or account is None:
            if account is not None:
                self._log_event(account.account_id, "sign_in_failed")
            return None

        if passwords.needs_rehash(stored):
            # They have just proved they know it, which is the only moment the plaintext is
            # available to upgrade the stored cost.
            account.password_hash = passwords.hash_password(password)

        token = self.create_session(account.account_id, days=WEB_SESSION_DAYS)
        self._log_event(account.account_id, "sign_in")
        return account, token

    def get_account(self, account_id: str) -> Account | None:
        """Get account by ID."""
        return self.session.query(Account).filter_by(account_id=account_id).first()

    def get_account_by_email(self, email: str) -> Account | None:
        """Get account by email."""
        return self.session.query(Account).filter_by(email=email).first()

    def get_account_by_oauth(
        self, oauth_provider: str, oauth_id: str
    ) -> Account | None:
        """Get account by OAuth provider and ID."""
        return (
            self.session.query(Account)
            .filter_by(oauth_provider=oauth_provider, oauth_id=oauth_id)
            .first()
        )

    def change_password(self, account_id: str, current: str, new: str) -> bool:
        """Replace a password, and sign every other session out.

        Changing a password is what someone does when they think a session is not theirs, so
        it has to actually end those sessions. The caller re-issues a session for whoever is
        still at the keyboard.
        """
        account = self.get_account(account_id)
        if account is None or not passwords.verify_password(current, account.password_hash):
            return False
        account.password_hash = passwords.hash_password(new)
        self.revoke_all_sessions(account_id)
        self._log_event(account_id, "password_changed")
        self.session.flush()
        return True

    # --- sessions -----------------------------------------------------------------------

    def create_session(
        self, account_id: str, *, device_id: str | None = None, days: int = WEB_SESSION_DAYS
    ) -> str:
        """Start a session and return its token. The token is not stored, only its hash."""
        token, token_hash = tokens.new_token()
        self.session.add(
            Session(
                token_hash=token_hash,
                account_id=account_id,
                device_id=device_id,
                expires_at=datetime.now(UTC) + timedelta(days=days),
            )
        )
        self.session.flush()
        return token

    def authenticate(self, token: str) -> Session | None:
        """Resolve a bearer token to a live session, or None."""
        row = (
            self.session.query(Session)
            .filter_by(token_hash=tokens.hash_token(token))
            .first()
        )
        if row is None or row.revoked_at is not None:
            return None
        if datetime.now(UTC) > _aware(row.expires_at):
            return None
        row.last_used_at = datetime.now(UTC)
        if row.device_id:
            self.update_device_last_seen(row.device_id)
        return row

    def revoke_session(self, token: str) -> bool:
        """Sign out. Idempotent: an already-dead token is not an error."""
        row = (
            self.session.query(Session)
            .filter_by(token_hash=tokens.hash_token(token))
            .first()
        )
        return self.revoke_session_row(row)

    def revoke_session_row(self, row: Session | None) -> bool:
        """Sign out a session already in hand, without hashing its token again."""
        if row is None or row.revoked_at is not None:
            return False
        row.revoked_at = datetime.now(UTC)
        self._log_event(row.account_id, "sign_out", device_id=row.device_id)
        self.session.flush()
        return True

    def revoke_all_sessions(self, account_id: str) -> int:
        now = datetime.now(UTC)
        live = (
            self.session.query(Session)
            .filter_by(account_id=account_id, revoked_at=None)
            .all()
        )
        for row in live:
            row.revoked_at = now
        self.session.flush()
        return len(live)

    # --- email verification -------------------------------------------------------------

    def create_email_verification(self, account_id: str, email: str) -> str:
        """Issue a verification link token for an address."""
        token, token_hash = tokens.new_token()
        self.session.add(
            EmailVerification(
                token_hash=token_hash,
                account_id=account_id,
                email=email,
                expires_at=datetime.now(UTC) + timedelta(hours=EMAIL_VERIFICATION_HOURS),
            )
        )
        self.session.flush()
        return token

    def verify_email(self, token: str) -> Account | None:
        """Redeem a verification link. Single use, and it expires."""
        row = (
            self.session.query(EmailVerification)
            .filter_by(token_hash=tokens.hash_token(token))
            .first()
        )
        if row is None or row.used_at is not None:
            return None
        if datetime.now(UTC) > _aware(row.expires_at):
            self._log_event(row.account_id, "email_verification_expired")
            return None

        account = self.get_account(row.account_id)
        if account is None or account.email != row.email:
            # The address moved on after the link was sent; proving the old one proves nothing.
            return None

        row.used_at = datetime.now(UTC)
        account.email_verified_at = datetime.now(UTC)
        self._log_event(account.account_id, "email_verified")
        self.session.flush()
        return account

    # --- devices ------------------------------------------------------------------------

    def add_device(self, account_id: str, device_id: str, device_name: str = "") -> Device:
        """Add a device to an account."""
        device = Device(
            device_id=device_id,
            account_id=account_id,
            device_name=device_name or "Unnamed device",
            last_seen=datetime.now(UTC),
        )
        self.session.add(device)
        self.session.flush()

        self._log_event(account_id, "device_added", device_id=device_id)

        return device

    def list_devices(self, account_id: str) -> list[Device]:
        return (
            self.session.query(Device)
            .filter_by(account_id=account_id)
            .order_by(Device.created_at)
            .all()
        )

    def get_device(self, device_id: str) -> Device | None:
        return self.session.query(Device).filter_by(device_id=device_id).first()

    def update_device_last_seen(self, device_id: str) -> None:
        """Update device's last_seen timestamp."""
        device = self.session.query(Device).filter_by(device_id=device_id).first()
        if device:
            device.last_seen = datetime.now(UTC)
            self.session.flush()

    def rename_device(self, account_id: str, device_id: str, name: str) -> Device | None:
        device = (
            self.session.query(Device)
            .filter_by(device_id=device_id, account_id=account_id)
            .first()
        )
        if device is None:
            return None
        device.device_name = name
        self._log_event(account_id, "device_renamed", device_id=device_id)
        self.session.flush()
        return device

    def revoke_device(self, account_id: str, device_id: str) -> Device | None:
        """Cut a device off, and end the sessions it was using.

        Revoking without ending the sessions would leave the device working until its token
        happened to expire, which is not what anyone means by the word.
        """
        device = (
            self.session.query(Device)
            .filter_by(device_id=device_id, account_id=account_id)
            .first()
        )
        if device is None or device.revoked_at is not None:
            return None
        now = datetime.now(UTC)
        device.revoked_at = now
        for row in (
            self.session.query(Session)
            .filter_by(account_id=account_id, device_id=device_id, revoked_at=None)
            .all()
        ):
            row.revoked_at = now
        self._log_event(account_id, "device_revoked", device_id=device_id)
        self.session.flush()
        return device

    # --- pairing ------------------------------------------------------------------------

    def issue_pairing_code(
        self, account_id: str, expires_in_minutes: int = PAIRING_CODE_MINUTES
    ) -> PairingCode:
        """Create a pairing code for adding a new device, and return the whole row."""
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
        pairing = PairingCode(
            account_id=account_id,
            code=generate_pairing_code(),
            expires_at=expires_at,
        )
        self.session.add(pairing)
        self.session.flush()

        self._log_event(account_id, "pairing_code_generated")

        return pairing

    def create_pairing_code(
        self, account_id: str, expires_in_minutes: int = PAIRING_CODE_MINUTES
    ) -> str:
        """Create a pairing code for adding a new device."""
        return self.issue_pairing_code(account_id, expires_in_minutes).code

    def validate_pairing_code(self, code: str) -> PairingCode | None:
        """Validate and return a pairing code."""
        pairing = self.session.query(PairingCode).filter_by(code=code).first()

        if not pairing:
            self._count_failed_attempt()
            return None

        # Check if already used
        if pairing.used_at:
            self._log_event(pairing.account_id, "pairing_code_reused", details=f"code={code}")
            return None

        # Check if expired
        if datetime.now(UTC) > _aware(pairing.expires_at):
            self._log_event(pairing.account_id, "pairing_code_expired", details=f"code={code}")
            return None

        if pairing.failed_attempts >= MAX_PAIRING_ATTEMPTS:
            self._log_event(pairing.account_id, "pairing_code_burned", details=f"code={code}")
            return None

        return pairing

    def _count_failed_attempt(self) -> None:
        """Charge one wrong guess to every code currently alive.

        This is what keeps eight digits sufficient. A guesser cannot aim at a particular code,
        so each live code need only survive `MAX_PAIRING_ATTEMPTS` wrong guesses in its short
        life before it stops being redeemable — and the owner generates another.
        """
        now = datetime.now(UTC)
        for row in self.session.query(PairingCode).filter_by(used_at=None).all():
            if now <= _aware(row.expires_at):
                row.failed_attempts += 1
        self.session.flush()

    def use_pairing_code(self, code: str) -> bool:
        """Mark a pairing code as used."""
        pairing = self.session.query(PairingCode).filter_by(code=code).first()

        if not pairing:
            return False

        pairing.used_at = datetime.now(UTC)
        self.session.flush()

        self._log_event(pairing.account_id, "pairing_code_used", details=f"code={code}")

        return True

    def redeem_pairing_code(
        self, code: str, device_id: str, device_name: str = ""
    ) -> tuple[Device, str] | None:
        """Exchange a pairing code for a device registration and a session of its own.

        This is the whole of what a code buys: one device, one session. The code is spent
        before the session is issued, so two devices racing on the same code cannot both win.
        """
        pairing = self.validate_pairing_code(code.strip())
        if pairing is None:
            return None
        account_id = pairing.account_id
        self.use_pairing_code(pairing.code)

        device = self.get_device(device_id)
        if device is None:
            device = self.add_device(account_id, device_id, device_name)
        elif device.account_id != account_id:
            # This install is already someone else's device. Moving it silently would take it
            # off the first account without telling anyone.
            return None
        else:
            device.revoked_at = None
            device.last_seen = datetime.now(UTC)
            if device_name:
                device.device_name = device_name

        token = self.create_session(
            account_id, device_id=device.device_id, days=DEVICE_SESSION_DAYS
        )
        self._log_event(account_id, "device_paired", device_id=device.device_id)
        self.session.flush()
        return device, token

    # --- audit --------------------------------------------------------------------------

    def _log_event(
        self,
        account_id: str,
        event_type: str,
        device_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: str | None = None,
    ) -> None:
        """Log an audit event."""
        event = AuditEvent(
            account_id=account_id,
            event_type=event_type,
            device_id=device_id,
            ip_address=ip_address or self.ip_address,
            user_agent=user_agent or self.user_agent,
            details=details,
        )
        self.session.add(event)
        self.session.flush()

    def list_audit_events(self, account_id: str, limit: int = 100) -> list[AuditEvent]:
        return (
            self.session.query(AuditEvent)
            .filter_by(account_id=account_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .all()
        )
