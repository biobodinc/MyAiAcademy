"""Live system metrics for the dashboard (spec §84 "System: GPU 42%, RAM 11 GB").

Cheap and best-effort: every probe degrades to ``None`` rather than raising. Values are a
snapshot of the *whole machine*, not of MyAI alone; the dashboard says so.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import psutil

from myai_core.hardware._subprocess import ProbeUnavailableError
from myai_core.hardware.gpu import _probe_nvidia_smi
from myai_core.hardware.models import GpuInfo, MemoryInfo
from myai_core.schemas import ApiModel

log = logging.getLogger(__name__)


class GpuMetrics(ApiModel):
    name: str
    utilization_percent: float | None = None
    temperature_c: float | None = None
    vram_used_bytes: int | None = None
    vram_total_bytes: int | None = None
    source: str


class BatteryMetrics(ApiModel):
    percent: float | None = None
    plugged_in: bool | None = None
    seconds_left: int | None = None


class SystemMetrics(ApiModel):
    sampled_at: datetime
    cpu_percent: float | None = None
    memory: MemoryInfo
    memory_used_bytes: int | None = None
    memory_percent: float | None = None
    gpu: GpuMetrics | None = None
    battery: BatteryMetrics | None = None
    warnings: list[str]


def probe_metrics(known_gpus: list[GpuInfo] | None = None) -> SystemMetrics:
    """Sample the machine. ``known_gpus`` (from the last hardware scan) lets us name a GPU
    whose live telemetry is unavailable, without claiming numbers we do not have."""
    warnings: list[str] = []

    cpu_percent: float | None
    try:
        # interval=None returns the utilisation since the previous call; the first call
        # after start-up returns 0.0, which psutil documents and the UI tolerates.
        cpu_percent = float(psutil.cpu_percent(interval=None))
    except Exception as exc:
        warnings.append(f"CPU utilisation unavailable: {exc}")
        cpu_percent = None

    memory = MemoryInfo()
    used: int | None = None
    percent: float | None = None
    try:
        vm = psutil.virtual_memory()
        memory = MemoryInfo(total_bytes=int(vm.total), available_bytes=int(vm.available))
        used = int(vm.total - vm.available)
        percent = round(used / vm.total * 100, 1) if vm.total else None
    except Exception as exc:
        warnings.append(f"Memory usage unavailable: {exc}")

    gpu = _gpu_metrics(known_gpus or [], warnings)
    battery = _battery(warnings)

    return SystemMetrics(
        sampled_at=datetime.now(tz=UTC),
        cpu_percent=cpu_percent,
        memory=memory,
        memory_used_bytes=used,
        memory_percent=percent,
        gpu=gpu,
        battery=battery,
        warnings=warnings,
    )


def _gpu_metrics(known: list[GpuInfo], warnings: list[str]) -> GpuMetrics | None:
    try:
        live = _probe_nvidia_smi()
    except ProbeUnavailableError:
        live = []
    except Exception as exc:
        warnings.append(f"GPU telemetry failed: {exc}")
        live = []
    if live:
        best = max(live, key=lambda g: g.vram_total_bytes or 0)
        return GpuMetrics(
            name=best.name,
            utilization_percent=best.utilization_percent,
            temperature_c=best.temperature_c,
            vram_used_bytes=best.vram_used_bytes,
            vram_total_bytes=best.vram_total_bytes,
            source=best.source,
        )
    if known:
        best = max(known, key=lambda g: g.vram_total_bytes or 0)
        # No live counters for this vendor/driver: report the name only.
        return GpuMetrics(name=best.name, vram_total_bytes=best.vram_total_bytes, source="scan")
    return None


def _battery(warnings: list[str]) -> BatteryMetrics | None:
    try:
        info = psutil.sensors_battery()
    except Exception as exc:
        warnings.append(f"Battery state unavailable: {exc}")
        return None
    if info is None:
        return None
    secs = info.secsleft
    seconds_left = int(secs) if isinstance(secs, int | float) and secs >= 0 else None
    return BatteryMetrics(
        percent=float(info.percent) if info.percent is not None else None,
        plugged_in=bool(info.power_plugged) if info.power_plugged is not None else None,
        seconds_left=seconds_left,
    )
