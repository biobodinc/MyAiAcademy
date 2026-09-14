"""Service layer for account management."""

import random
import string
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from myai_server.models import Account, Device, PairingCode, AuditEvent


def generate_account_id() -> str:
    """Generate a 16-digit random account ID."""
    return "".join(random.choices(string.digits, k=16))


def generate_pairing_code() -> str:
    """Generate an 8-digit pairing code."""
    return "".join(random.choices(string.digits, k=8))


class AccountService:
    """Account management service."""

    def __init__(self, session: Session):
        self.session = session

    def create_account(
        self,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        oauth_provider: Optional[str] = None,
        oauth_id: Optional[str] = None,
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

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self.session.query(Account).filter_by(account_id=account_id).first()

    def get_account_by_email(self, email: str) -> Optional[Account]:
        """Get account by email."""
        return self.session.query(Account).filter_by(email=email).first()

    def get_account_by_oauth(
        self, oauth_provider: str, oauth_id: str
    ) -> Optional[Account]:
        """Get account by OAuth provider and ID."""
        return (
            self.session.query(Account)
            .filter_by(oauth_provider=oauth_provider, oauth_id=oauth_id)
            .first()
        )

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

    def update_device_last_seen(self, device_id: str) -> None:
        """Update device's last_seen timestamp."""
        device = self.session.query(Device).filter_by(device_id=device_id).first()
        if device:
            device.last_seen = datetime.now(UTC)
            self.session.flush()

    def create_pairing_code(self, account_id: str, expires_in_minutes: int = 10) -> str:
        """Create a pairing code for adding a new device."""
        code = generate_pairing_code()
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)

        pairing = PairingCode(
            account_id=account_id,
            code=code,
            expires_at=expires_at,
        )
        self.session.add(pairing)
        self.session.flush()

        self._log_event(account_id, "pairing_code_generated")

        return code

    def validate_pairing_code(self, code: str) -> Optional[PairingCode]:
        """Validate and return a pairing code."""
        pairing = self.session.query(PairingCode).filter_by(code=code).first()

        if not pairing:
            return None

        # Check if already used
        if pairing.used_at:
            self._log_event(pairing.account_id, "pairing_code_reused", details=f"code={code}")
            return None

        # Check if expired
        if datetime.now(UTC) > pairing.expires_at:
            self._log_event(pairing.account_id, "pairing_code_expired", details=f"code={code}")
            return None

        return pairing

    def use_pairing_code(self, code: str) -> bool:
        """Mark a pairing code as used."""
        pairing = self.session.query(PairingCode).filter_by(code=code).first()

        if not pairing:
            return False

        pairing.used_at = datetime.now(UTC)
        self.session.flush()

        self._log_event(pairing.account_id, "pairing_code_used", details=f"code={code}")

        return True

    def _log_event(
        self,
        account_id: str,
        event_type: str,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        """Log an audit event."""
        event = AuditEvent(
            account_id=account_id,
            event_type=event_type,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        self.session.add(event)
        self.session.flush()
