"""Storage root configuration and usage accounting."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.db.models import StorageConfig
from myai_core.hardware.models import StorageVolume
from myai_core.storage.layout import (
    PROTECTED_CATEGORIES,
    ROOT_MARKER_FILE,
    STORAGE_CATEGORIES,
    StorageCategory,
)
from myai_core.storage.models import (
    CategoryUsage,
    StorageLocationCheck,
    StorageOverview,
)

MIN_FREE_BYTES_WARN = 20 * 1024**3  # models alone are routinely > 5 GB

VolumesProbe = Callable[[], tuple[list[StorageVolume], list[str]]]


class StorageManager:
    def __init__(self, session: Session, volumes_probe: VolumesProbe) -> None:
        self._session = session
        self._volumes_probe = volumes_probe

    # --- configuration --------------------------------------------------------------

    def get_config(self) -> StorageConfig | None:
        return self._session.scalar(select(StorageConfig).where(StorageConfig.id == 1))

    def check_location(self, candidate: str) -> StorageLocationCheck:
        """Validate a candidate root without changing anything."""
        path = Path(candidate).expanduser()
        result = StorageLocationCheck(path=str(path), ok=True)

        if not path.is_absolute():
            result.problems.append("Path must be absolute.")
        anchor = _nearest_existing_parent(path)
        if anchor is None:
            result.problems.append("No part of the path exists yet.")
        elif not os.access(anchor, os.W_OK):
            result.problems.append("That location is not writable by the current user.")

        if path.exists() and not path.is_dir():
            result.problems.append("Path exists and is not a directory.")

        if path.is_dir() and (path / ROOT_MARKER_FILE).is_file():
            result.is_existing_myai_storage = True
        elif path.is_dir() and any(path.iterdir()):
            result.problems.append(
                "Directory is not empty and is not existing MyAI storage. "
                "Choose an empty folder or a new sub-folder."
            )

        volume = self._volume_for(path)
        if volume is not None:
            result.free_bytes = volume.free_bytes
            result.total_bytes = volume.total_bytes
            result.is_removable = volume.is_removable
            if volume.free_bytes is not None and volume.free_bytes < MIN_FREE_BYTES_WARN:
                result.problems.append(
                    "Less than 20 GB free. Models and training data will not fit comfortably."
                )

        result.ok = not any(
            p for p in result.problems if not p.startswith("Less than")
        )  # low space is a warning, not a blocker
        return result

    def configure_root(self, candidate: str) -> StorageConfig:
        """Set (or move) the storage root and create the managed layout."""
        check = self.check_location(candidate)
        if not check.ok:
            raise StorageError("; ".join(check.problems))
        root = Path(check.path)
        _create_layout(root)

        config = self.get_config()
        if config is None:
            config = StorageConfig(id=1, root_path=str(root), category_overrides={})
            self._session.add(config)
        else:
            config.root_path = str(root)
        self._session.flush()
        return config

    def set_category_override(self, category: StorageCategory, path: str | None) -> StorageConfig:
        config = self._require_config()
        overrides = dict(config.category_overrides)
        if path is None:
            overrides.pop(category.value, None)
        else:
            target = Path(path).expanduser()
            if not target.is_absolute():
                raise StorageError("Override path must be absolute.")
            target.mkdir(parents=True, exist_ok=True)
            overrides[category.value] = str(target)
        config.category_overrides = overrides
        self._session.flush()
        return config

    # --- paths ------------------------------------------------------------------------

    def category_path(self, category: StorageCategory) -> Path:
        config = self._require_config()
        override = config.category_overrides.get(category.value)
        if override:
            return Path(override)
        return Path(config.root_path) / STORAGE_CATEGORIES[category]

    # --- accounting -------------------------------------------------------------------

    def overview(self) -> StorageOverview:
        config = self.get_config()
        if config is None:
            return StorageOverview(
                configured=False, root_path=None, categories=[], total_bytes_used=0
            )
        usages: list[CategoryUsage] = []
        for category in StorageCategory:
            path = self.category_path(category)
            size, count = _directory_usage(path)
            usages.append(
                CategoryUsage(
                    category=category,
                    path=str(path),
                    bytes_used=size,
                    file_count=count,
                    exists=path.is_dir(),
                    protected=category in PROTECTED_CATEGORIES,
                )
            )
        volume = self._volume_for(Path(config.root_path))
        return StorageOverview(
            configured=True,
            root_path=config.root_path,
            categories=usages,
            total_bytes_used=sum(u.bytes_used for u in usages),
            volume_total_bytes=volume.total_bytes if volume else None,
            volume_free_bytes=volume.free_bytes if volume else None,
            configured_at=config.configured_at,
            category_overrides=dict(config.category_overrides),
        )

    def detect_external_candidates(self) -> list[StorageVolume]:
        """Removable volumes worth offering to the user (spec §22)."""
        volumes, _ = self._volumes_probe()
        return [v for v in volumes if v.is_removable]

    # --- internals --------------------------------------------------------------------

    def _require_config(self) -> StorageConfig:
        config = self.get_config()
        if config is None:
            raise StorageError("MyAI storage has not been configured yet.")
        return config

    def _volume_for(self, path: Path) -> StorageVolume | None:
        volumes, _ = self._volumes_probe()
        anchor = _nearest_existing_parent(path) or path
        best: StorageVolume | None = None
        for volume in volumes:
            mount = Path(volume.mountpoint)
            try:
                anchor.resolve().relative_to(mount.resolve())
            except (ValueError, OSError):
                continue
            if best is None or len(str(mount)) > len(best.mountpoint):
                best = volume
        return best


class StorageError(ValueError):
    """User-facing storage configuration problem."""


def _nearest_existing_parent(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return None


def _create_layout(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for folder in STORAGE_CATEGORIES.values():
        (root / folder).mkdir(exist_ok=True)
    marker = root / ROOT_MARKER_FILE
    if not marker.exists():
        marker.write_text(
            "This folder is managed by MyAI Academy. Do not rename the sub-folders.\n",
            encoding="utf-8",
        )


def _directory_usage(path: Path) -> tuple[int, int]:
    """Total bytes and file count under ``path`` (no symlink following)."""
    if not path.is_dir():
        return 0, 0
    total = 0
    count = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            count += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, count
