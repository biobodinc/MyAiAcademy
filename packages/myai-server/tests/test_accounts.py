"""Tests for account creation, pairing, and device management."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from myai_server.db import Base
from myai_server.models import PairingCode
from myai_server.services import AccountService, generate_account_id, generate_pairing_code


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def test_account_id_generation():
    """Account ID should be 16 digits."""
    account_id = generate_account_id()
    assert len(account_id) == 16
    assert account_id.isdigit()


def test_pairing_code_generation():
    """Pairing code should be 8 digits."""
    code = generate_pairing_code()
    assert len(code) == 8
    assert code.isdigit()


def test_create_account_with_email(in_memory_db):
    """Create account with email and password."""
    service = AccountService(in_memory_db)
    account = service.create_account(
        email="test@example.com",
        password_hash="hashed_password",
    )

    assert account.account_id
    assert len(account.account_id) == 16
    assert account.email == "test@example.com"
    assert account.password_hash == "hashed_password"
    assert account.oauth_provider is None


def test_create_account_with_oauth(in_memory_db):
    """Create account with OAuth provider."""
    service = AccountService(in_memory_db)
    account = service.create_account(
        oauth_provider="google",
        oauth_id="google_12345",
    )

    assert account.account_id
    assert account.oauth_provider == "google"
    assert account.oauth_id == "google_12345"
    assert account.email is None


def test_get_account_by_id(in_memory_db):
    """Retrieve account by ID."""
    service = AccountService(in_memory_db)
    created = service.create_account(email="test@example.com", password_hash="hash")
    in_memory_db.commit()

    found = service.get_account(created.account_id)
    assert found is not None
    assert found.account_id == created.account_id
    assert found.email == "test@example.com"


def test_get_account_by_email(in_memory_db):
    """Retrieve account by email."""
    service = AccountService(in_memory_db)
    created = service.create_account(email="test@example.com", password_hash="hash")
    in_memory_db.commit()

    found = service.get_account_by_email("test@example.com")
    assert found is not None
    assert found.account_id == created.account_id


def test_add_device(in_memory_db):
    """Add a device to an account."""
    service = AccountService(in_memory_db)
    account = service.create_account(email="test@example.com", password_hash="hash")
    in_memory_db.commit()

    device = service.add_device(
        account.account_id, device_id="inst_abc123", device_name="My Laptop"
    )

    assert device.device_id == "inst_abc123"
    assert device.account_id == account.account_id
    assert device.device_name == "My Laptop"
    assert device.last_seen is not None


def test_create_pairing_code(in_memory_db):
    """Generate a pairing code for an account."""
    service = AccountService(in_memory_db)
    account = service.create_account(email="test@example.com", password_hash="hash")
    in_memory_db.commit()

    code = service.create_pairing_code(account.account_id, expires_in_minutes=10)

    assert len(code) == 8
    assert code.isdigit()

    pairing = in_memory_db.query(PairingCode).filter_by(code=code).first()
    assert pairing is not None
    assert pairing.account_id == account.account_id
    assert pairing.used_at is None


def test_validate_pairing_code(in_memory_db):
    """Validate a pairing code before using it."""
    service = AccountService(in_memory_db)
    account = service.create_account(email="test@example.com", password_hash="hash")
    in_memory_db.commit()

    code = service.create_pairing_code(account.account_id, expires_in_minutes=10)
    in_memory_db.commit()

    pairing = service.validate_pairing_code(code)
    assert pairing is not None
    assert pairing.code == code
    assert pairing.used_at is None


def test_pairing_code_reuse_fails(in_memory_db):
    """Cannot reuse a pairing code."""
    service = AccountService(in_memory_db)
    account = service.create_account(email="test@example.com", password_hash="hash")
    in_memory_db.commit()

    code = service.create_pairing_code(account.account_id, expires_in_minutes=10)
    in_memory_db.commit()

    # Mark as used
    service.use_pairing_code(code)
    in_memory_db.commit()

    # Try to validate again
    pairing = service.validate_pairing_code(code)
    assert pairing is None


def test_expired_pairing_code_fails(in_memory_db):
    """Cannot use an expired pairing code."""
    service = AccountService(in_memory_db)
    account = service.create_account(email="test@example.com", password_hash="hash")
    in_memory_db.commit()

    # Create code that expires in past
    code = service.create_pairing_code(account.account_id, expires_in_minutes=-1)
    in_memory_db.commit()

    # Try to validate
    pairing = service.validate_pairing_code(code)
    assert pairing is None


def test_audit_log_on_account_creation(in_memory_db):
    """Account creation is logged in audit events."""
    service = AccountService(in_memory_db)
    account = service.create_account(email="test@example.com", password_hash="hash")
    in_memory_db.commit()

    from myai_server.models import AuditEvent

    events = (
        in_memory_db.query(AuditEvent)
        .filter_by(account_id=account.account_id, event_type="sign_up")
        .all()
    )

    assert len(events) == 1
    assert events[0].event_type == "sign_up"
