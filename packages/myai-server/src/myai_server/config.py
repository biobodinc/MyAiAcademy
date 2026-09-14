"""Server settings, all of them from the environment.

Nothing here has a secret as a default. A missing password gives an empty string and a
connection that fails loudly, which is the right outcome — a default that happens to work
locally is how a development credential ends up in production.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _origins() -> list[str]:
    raw = os.getenv("MYAI_SERVER_CORS_ORIGINS", "")
    return [item.strip() for item in raw.split(",") if item.strip()] or ["http://localhost:3000"]


@dataclass(frozen=True, slots=True)
class ServerSettings:
    postgres_host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: str = field(default_factory=lambda: os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "myai_academy"))
    postgres_user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    postgres_password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))

    base_url: str = field(
        default_factory=lambda: os.getenv("MYAI_SERVER_BASE_URL", "http://localhost:3000")
    )
    """Where the website lives. Verification links are built against this."""

    cors_origins: list[str] = field(default_factory=_origins)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
