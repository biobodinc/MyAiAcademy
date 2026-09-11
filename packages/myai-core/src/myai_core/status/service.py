from __future__ import annotations

import socket
import threading
import time
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from myai_core import __version__


class Availability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    UNKNOWN = "unknown"


class ServiceStatus(BaseModel):
    service_version: str
    started_at: datetime
    uptime_seconds: float
    internet: Availability = Field(description="Reachability of the public internet.")
    internet_checked_at: datetime | None
    ai: Availability = Field(description="Whether a local model is set up and loadable.")
    ai_detail: str
    training: Availability
    training_detail: str
    profile_exists: bool
    storage_configured: bool
    onboarding_completed: bool
    privacy_mode: str
    cloud_uploads: int = Field(
        default=0, description="Private AI data uploads made by this service. Always 0 in Phase 1."
    )


class InternetMonitor:
    """Cheap, cached TCP reachability check. Never blocks a request for long.

    Uses a TCP connect (no HTTP, no payload, no DNS-less trickery) against well-known
    public resolvers on port 53. This sends no user data anywhere; it only answers
    "can this machine reach the internet at all?".
    """

    _TARGETS = (("1.1.1.1", 53), ("8.8.8.8", 53), ("9.9.9.9", 53))

    def __init__(self, ttl_seconds: float = 30.0, timeout: float = 1.5) -> None:
        self._ttl = ttl_seconds
        self._timeout = timeout
        self._lock = threading.Lock()
        self._state = Availability.UNKNOWN
        self._checked_at: datetime | None = None
        self._checked_monotonic = 0.0

    def current(self) -> tuple[Availability, datetime | None]:
        with self._lock:
            fresh = (time.monotonic() - self._checked_monotonic) < self._ttl
            if fresh:
                return self._state, self._checked_at
        state = self._probe()
        with self._lock:
            self._state = state
            self._checked_at = datetime.now(tz=UTC)
            self._checked_monotonic = time.monotonic()
            return self._state, self._checked_at

    def _probe(self) -> Availability:
        for host, port in self._TARGETS:
            try:
                with socket.create_connection((host, port), timeout=self._timeout):
                    return Availability.AVAILABLE
            except OSError:
                continue
        return Availability.UNAVAILABLE


class StatusService:
    def __init__(self, internet: InternetMonitor, started_at: datetime) -> None:
        self._internet = internet
        self._started_at = started_at

    def build(
        self,
        *,
        profile_exists: bool,
        storage_configured: bool,
        onboarding_completed: bool,
        privacy_mode: str,
    ) -> ServiceStatus:
        internet, checked_at = self._internet.current()
        now = datetime.now(tz=UTC)
        return ServiceStatus(
            service_version=__version__,
            started_at=self._started_at,
            uptime_seconds=(now - self._started_at).total_seconds(),
            internet=internet,
            internet_checked_at=checked_at,
            ai=Availability.NOT_CONFIGURED,
            ai_detail="No local model is set up yet. Local chat arrives in Phase 2.",
            training=Availability.UNAVAILABLE,
            training_detail="Training jobs arrive in Phase 4.",
            profile_exists=profile_exists,
            storage_configured=storage_configured,
            onboarding_completed=onboarding_completed,
            privacy_mode=privacy_mode,
            cloud_uploads=0,
        )

    @staticmethod
    def labels(status: ServiceStatus) -> dict[str, object]:
        """Compact, display-ready view used by ``/status``."""
        internet = {
            Availability.AVAILABLE: "Online",
            Availability.UNAVAILABLE: "Offline",
        }.get(status.internet, "Unknown")
        return {
            "ai_label": "Not configured (Phase 2)"
            if status.ai is Availability.NOT_CONFIGURED
            else status.ai.value.title(),
            "internet_label": internet,
            "training_label": "Unavailable (Phase 4)",
            "privacy_mode": status.privacy_mode,
            "cloud_uploads": status.cloud_uploads,
        }
