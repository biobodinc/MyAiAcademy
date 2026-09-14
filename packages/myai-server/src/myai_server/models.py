"""Database models for the central account server."""

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    """A user account on the central server."""

    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    """16-digit random account identifier, human-readable."""

    email: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)
    """Email address (nullable if using OAuth only)."""

    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    """Hashed password (nullable if using OAuth)."""

    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    """OAuth provider: 'google', 'apple', 'facebook'."""

    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    """OAuth provider's user ID."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    devices: Mapped[list["Device"]] = relationship(
        "Device", back_populates="account", cascade="all, delete-orphan"
    )
    pairing_codes: Mapped[list["PairingCode"]] = relationship(
        "PairingCode", back_populates="account", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="account", cascade="all, delete-orphan"
    )


class Device(Base):
    """A device linked to an account."""

    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    """Installation-specific device ID (from sync_identity.install_id)."""

    account_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("accounts.account_id"), nullable=False
    )
    """Account this device belongs to."""

    device_name: Mapped[str] = mapped_column(String(255), default="Unnamed device")
    """User-friendly name (e.g., 'My MacBook', 'iPhone')."""

    last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    account: Mapped["Account"] = relationship("Account", back_populates="devices")


class PairingCode(Base):
    """Temporary 8-digit code for adding a new device to an account."""

    __tablename__ = "pairing_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("accounts.account_id"), nullable=False
    )

    code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    """8-digit pairing code, single-use."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """Code expires after 10 minutes."""

    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """When the code was used (None if unused)."""

    account: Mapped["Account"] = relationship("Account", back_populates="pairing_codes")


class AuditEvent(Base):
    """Audit log of account activities."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("accounts.account_id"), nullable=False
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    """Event type: 'sign_up', 'sign_in', 'device_added', 'device_removed', 'pairing_attempted', etc."""

    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    """Device involved in the event (if applicable)."""

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    """IP address of the request (IPv4 or IPv6)."""

    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    """User-Agent header from the request."""

    details: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    """Additional event details (JSON-serialized if needed)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    account: Mapped["Account"] = relationship("Account", back_populates="audit_events")
