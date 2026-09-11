"""Mounted storage volumes, with a best-effort "removable" flag for spec §22."""

from __future__ import annotations

import ctypes
import platform
from pathlib import Path

import psutil

from myai_core.hardware.models import StorageVolume

_WIN_DRIVE_REMOVABLE = 2
_LINUX_REMOVABLE_MOUNT_PREFIXES = ("/media/", "/run/media/", "/mnt/")


def probe_volumes() -> tuple[list[StorageVolume], list[str]]:
    warnings: list[str] = []
    volumes: list[StorageVolume] = []
    try:
        partitions = psutil.disk_partitions(all=False)
    except OSError as exc:
        return [], [f"disk_partitions failed: {exc}"]

    for part in partitions:
        if _is_pseudo_filesystem(part.fstype):
            continue
        volume = StorageVolume(
            mountpoint=part.mountpoint, device=part.device or None, filesystem=part.fstype or None
        )
        try:
            usage = psutil.disk_usage(part.mountpoint)
            volume.total_bytes = int(usage.total)
            volume.free_bytes = int(usage.free)
        except OSError as exc:
            warnings.append(f"{part.mountpoint}: usage unavailable ({exc})")
        volume.is_removable = _is_removable(part.mountpoint, part.device)
        volumes.append(volume)
    return volumes, warnings


def _is_pseudo_filesystem(fstype: str) -> bool:
    return fstype in {"squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs", "cgroup2"}


def _is_removable(mountpoint: str, device: str) -> bool | None:
    system = platform.system()
    if system == "Windows":
        return _is_removable_windows(mountpoint)
    if system == "Linux":
        return _is_removable_linux(mountpoint, device)
    if system == "Darwin":
        # Anything under /Volumes that is not the boot volume is external or an image.
        # Without IOKit we cannot distinguish USB from a mounted DMG, so report unknown.
        return None
    return None


def _is_removable_windows(mountpoint: str) -> bool | None:
    # ``ctypes.windll`` exists only on Windows, so it is read dynamically: a static
    # reference is an error when type-checking on Windows and needs an ignore that is
    # itself an error when type-checking anywhere else.
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return None
    try:
        drive_type = windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(mountpoint))
    except (AttributeError, OSError):
        return None
    return bool(drive_type == _WIN_DRIVE_REMOVABLE)


def _is_removable_linux(mountpoint: str, device: str) -> bool | None:
    # /sys/block/<disk>/removable is authoritative when we can map the partition back.
    name = Path(device).name
    base = name.rstrip("0123456789")
    if base.endswith("p") and name[-1].isdigit():  # nvme0n1p1 -> nvme0n1
        base = base[:-1]
    for candidate in (base, name):
        sys_file = Path("/sys/block") / candidate / "removable"
        try:
            return sys_file.read_text(encoding="utf-8").strip() == "1"
        except OSError:
            continue
    if mountpoint.startswith(_LINUX_REMOVABLE_MOUNT_PREFIXES):
        return True
    return None
