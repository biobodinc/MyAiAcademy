"""Database models for the central account server."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
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

    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """Hashed password (nullable if using OAuth)."""

    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    """OAuth provider: 'google', 'apple', 'facebook'."""

    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """OAuth provider's user ID."""

    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """When the address was proven. None means the sign-up link has not been followed yet."""

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
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="account", cascade="all, delete-orphan"
    )
    email_verifications: Mapped[list["EmailVerification"]] = relationship(
        "EmailVerification", back_populates="account", cascade="all, delete-orphan"
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

    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """When this device was cut off. Revoked devices are kept, not deleted, so that the
    audit log still has something to point at and so a name cannot be quietly reused."""

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

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """When the code was used (None if unused)."""

    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    """Wrong guesses seen while this code was alive — not wrong guesses *at* this code.

    Someone guessing does not know which codes exist, so every wrong guess is an attempt at
    all of them. Counting it against each live code caps the total guesses any one code has to
    survive, which eight digits alone would not do at machine speed."""

    account: Mapped["Account"] = relationship("Account", back_populates="pairing_codes")


class AuditEvent(Base):
    """Audit log of account activities."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("accounts.account_id"), nullable=False
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    """Event type: 'sign_up', 'sign_in', 'device_added', 'device_revoked', and so on."""

    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """Device involved in the event (if applicable)."""

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    """IP address of the request (IPv4 or IPv6)."""

    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    """User-Agent header from the request."""

    details: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    """Additional event details (JSON-serialized if needed)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    account: Mapped["Account"] = relationship("Account", back_populates="audit_events")


class Session(Base):
    """A signed-in session. The token itself is never stored — only its SHA-256."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)

    account_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("accounts.account_id"), nullable=False, index=True
    )

    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """The device this session belongs to, when it was created by pairing rather than by
    signing in on the website."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """Set by signing out, or by revoking the device this session belongs to."""

    account: Mapped["Account"] = relationship("Account", back_populates="sessions")


class EmailVerification(Base):
    """A single-use link proving that whoever signed up can read that inbox.

    Kept in its own table rather than as columns on the account so that a re-send does not
    overwrite the outstanding link, and so a later change of address can be verified without
    disturbing the address already in use.
    """

    __tablename__ = "email_verifications"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)

    account_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("accounts.account_id"), nullable=False, index=True
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    """The address being proven, recorded here so a pending link cannot be redirected by
    changing the address on the account after the fact."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["Account"] = relationship("Account", back_populates="email_verifications")
