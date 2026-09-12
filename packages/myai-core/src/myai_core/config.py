"""Service configuration.

Everything here is *non-secret* runtime configuration. Secrets (the local API token) are
generated at first run and live only in the app data directory; see
:mod:`myai_core.security.local_token`.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 41337
"""Default local API port. Chosen from the IANA dynamic/private range (>= 49152 is
ephemeral on most OSes; 41337 sits in the registered range with no well-known holder).
If it is busy the service picks a free port and records it in the discovery file."""


class CoreSettings(BaseSettings):
    """Runtime settings, overridable via ``MYAI_CORE_*`` environment variables.

    ``host`` is intentionally restricted to loopback addresses (spec §47, §73), and no
    setting can change that. Letting a phone reach this service is a *separate* listener
    (``lan_enabled``): HTTPS only, off unless the user turns it on, and it refuses the
    installation token so the master key never leaves this machine.
    """

    model_config = SettingsConfigDict(env_prefix="MYAI_CORE_", extra="ignore")

    host: str = LOOPBACK_HOST
    port: int = Field(default=DEFAULT_PORT, ge=1024, le=65535)
    log_level: str = "info"
    dev_cors_origins: tuple[str, ...] = ("http://localhost:1420", "http://127.0.0.1:1420")
    """Vite dev-server origins allowed in addition to the packaged Tauri origins."""

    lan_enabled: bool = False
    """Whether paired devices on this network may reach the service. Off by default."""
    lan_host: str = "0.0.0.0"  # noqa: S104 - the point of this listener is to be reachable
    lan_port: int = Field(default=DEFAULT_PORT + 1, ge=1024, le=65535)

    @field_validator("host")
    @classmethod
    def _loopback_only(cls, value: str) -> str:
        if value not in {"127.0.0.1", "::1", "localhost"}:
            msg = "The local API may only bind to a loopback address (127.0.0.1, ::1, localhost)."
            raise ValueError(msg)
        return value


TAURI_ORIGINS: tuple[str, ...] = (
    "tauri://localhost",  # macOS / Linux packaged webview
    "http://tauri.localhost",  # Windows (WebView2) packaged webview
    "https://tauri.localhost",
)
