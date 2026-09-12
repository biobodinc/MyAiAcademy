"""Are this installation's secrets actually stored safely? (spec §60 secure storage)

The local API token is the key to everything this service can do, so where it lives and
who can read it is a security property worth checking rather than assuming. On POSIX that
is a permission bit test with a definite answer. On Windows it is not: NTFS access is
governed by ACLs that a mode bit does not describe, so this reports what it can verify and
says plainly when it cannot verify anything, instead of showing a reassuring tick.

Nothing here reads or logs a secret. It looks at metadata only.
"""

from __future__ import annotations

import contextlib
import stat
import sys
from pathlib import Path

from pydantic import Field

from myai_core.paths import AppPaths
from myai_core.schemas import ApiModel

GROUP_OR_WORLD = stat.S_IRWXG | stat.S_IRWXO


class SecretStorageReport(ApiModel):
    """What was checked, what it found, and what could not be determined."""

    token_file_exists: bool
    owner_only: bool | None = Field(
        default=None,
        description="True when only the owner can read the secrets; None when unverifiable.",
    )
    data_dir_owner_only: bool | None = None
    mode: str | None = Field(default=None, description="Octal permissions, POSIX only.")
    checked: bool = Field(
        default=True, description="False on platforms where permissions cannot be read this way."
    )
    problems: list[str] = Field(default_factory=list)
    detail: str = ""


def check_secret_storage(paths: AppPaths) -> SecretStorageReport:
    """Report what can be verified about who can read this installation's secrets.

    Written as an if/else on the platform so that the branch a given platform cannot take
    is understood as such by a type checker, instead of looking like dead code.
    """
    if sys.platform == "win32":
        return SecretStorageReport(
            token_file_exists=paths.token_file.is_file(),
            checked=False,
            detail=(
                "On Windows the data directory is protected by the account it belongs to. "
                "Access here is governed by ACLs, which this check cannot read, so no claim "
                "is made either way. Keep a password on your Windows account."
            ),
        )
    else:
        return _check_posix(paths)


def _check_posix(paths: AppPaths) -> SecretStorageReport:
    token_file = paths.token_file
    exists = token_file.is_file()
    problems: list[str] = []
    mode: str | None = None
    owner_only: bool | None = None
    if exists:
        file_mode = stat.S_IMODE(token_file.stat().st_mode)
        mode = oct(file_mode)
        owner_only = not (file_mode & GROUP_OR_WORLD)
        if not owner_only:
            problems.append(
                f"{token_file.name} can be read by other users on this machine "
                f"(permissions {mode}). It should be 0o600."
            )

    dir_owner_only: bool | None = None
    if paths.data_dir.is_dir():
        dir_mode = stat.S_IMODE(paths.data_dir.stat().st_mode)
        dir_owner_only = not (dir_mode & GROUP_OR_WORLD)
        if not dir_owner_only:
            problems.append(
                f"The data directory is reachable by other users (permissions {oct(dir_mode)}). "
                "It should be 0o700."
            )

    return SecretStorageReport(
        token_file_exists=exists,
        owner_only=owner_only,
        data_dir_owner_only=dir_owner_only,
        mode=mode,
        problems=problems,
        detail=(
            "Only your account can read this installation's token and database."
            if not problems
            else "Something else on this machine can read secrets that should be yours alone."
        ),
    )


def repair_secret_storage(paths: AppPaths) -> list[str]:
    """Tighten permissions that are looser than they should be. Returns what was changed.

    Run at start-up: a data directory copied, restored from a backup or unpacked from an
    archive can easily arrive group-readable, and carrying on with a token anyone on the
    machine can read would be the wrong kind of quiet.
    """
    if sys.platform == "win32":
        return []  # nothing to tighten: ACLs, not mode bits, govern access here
    else:
        return _repair_posix(paths)


def _repair_posix(paths: AppPaths) -> list[str]:
    changed: list[str] = []
    for target, wanted in ((paths.data_dir, 0o700), (paths.token_file, 0o600)):
        try:
            current = stat.S_IMODE(target.stat().st_mode)
        except OSError:
            continue
        if current & GROUP_OR_WORLD:
            try:
                target.chmod(wanted)
            except OSError as exc:  # pragma: no cover - unusual filesystem
                changed.append(f"could not tighten {target.name}: {exc}")
                continue
            changed.append(f"{target.name}: {oct(current)} -> {oct(wanted)}")
    return changed


def restrict_new_file(path: Path) -> None:
    """Make a file owner-only, where the platform supports it."""
    if sys.platform != "win32":
        with contextlib.suppress(OSError):
            path.chmod(0o600)
