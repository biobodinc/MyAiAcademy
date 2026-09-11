"""Filesystem locations owned by the core service.

Two distinct roots exist and must not be confused:

* **App data directory** – small, per-user, OS-conventional (``platformdirs``). Holds the
  SQLite database, the local API token, logs and the service discovery file. Users do not
  normally pick this location.
* **MyAI storage root** – large, user-chosen (spec §21/§22). Holds models, training data,
  checkpoints, generated media, and so on. Managed by :mod:`myai_core.storage`.

Only the app data directory is resolved here; the storage root is user configuration.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs

APP_NAME = "MyAI Academy"
APP_AUTHOR = "MyAI Academy"

ENV_DATA_DIR = "MYAI_DATA_DIR"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved per-installation paths for the core service."""

    data_dir: Path

    @property
    def database_file(self) -> Path:
        return self.data_dir / "myai-core.sqlite3"

    @property
    def token_file(self) -> Path:
        return self.data_dir / "local-api.token"

    @property
    def discovery_file(self) -> Path:
        """Written by a running service so local clients can find its port."""
        return self.data_dir / "local-api.json"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure(self) -> AppPaths:
        """Create the data directory tree with owner-only permissions where supported."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        _restrict_to_owner(self.data_dir)
        return self


def resolve_app_paths(override: str | os.PathLike[str] | None = None) -> AppPaths:
    """Resolve the app data directory.

    Precedence: explicit ``override`` → ``MYAI_DATA_DIR`` env var → platform default.
    The env var exists for tests, portable installs and advanced users; it is never set by
    the application itself.
    """
    if override is not None:
        return AppPaths(Path(override).expanduser().resolve())
    env_value = os.environ.get(ENV_DATA_DIR)
    if env_value:
        return AppPaths(Path(env_value).expanduser().resolve())
    dirs = PlatformDirs(appname=APP_NAME, appauthor=APP_AUTHOR, roaming=False)
    return AppPaths(Path(dirs.user_data_dir))


def _restrict_to_owner(path: Path) -> None:
    """Best-effort ``chmod 700``. Windows ACLs are inherited from the user profile."""
    if os.name == "posix":
        # Some filesystems (e.g. FAT-formatted removable media) reject chmod. Not fatal.
        with contextlib.suppress(OSError):
            path.chmod(0o700)
