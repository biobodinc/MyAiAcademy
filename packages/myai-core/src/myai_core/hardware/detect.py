"""Orchestrates all probes into a single :class:`HardwareReport`."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from myai_core.hardware.cpu import probe_cpu
from myai_core.hardware.gpu import probe_gpus
from myai_core.hardware.memory import probe_memory
from myai_core.hardware.models import CpuInfo, HardwareReport, MemoryInfo, OsInfo
from myai_core.hardware.os_info import probe_os
from myai_core.hardware.tiers import estimate_tier
from myai_core.hardware.volumes import probe_volumes

log = logging.getLogger(__name__)


def detect_hardware() -> HardwareReport:
    warnings: list[str] = []

    try:
        os_info = probe_os()
    except Exception as exc:
        log.warning("OS probe failed", exc_info=exc)
        warnings.append(f"OS probe failed: {exc}")
        os_info = OsInfo(system="unknown")

    try:
        cpu = probe_cpu()
    except Exception as exc:
        log.warning("CPU probe failed", exc_info=exc)
        warnings.append(f"CPU probe failed: {exc}")
        cpu = CpuInfo()

    try:
        memory = probe_memory()
    except Exception as exc:
        log.warning("Memory probe failed", exc_info=exc)
        warnings.append(f"Memory probe failed: {exc}")
        memory = MemoryInfo()

    gpus, gpu_warnings = probe_gpus()
    warnings.extend(gpu_warnings)

    volumes, volume_warnings = probe_volumes()
    warnings.extend(volume_warnings)

    tier = estimate_tier(cpu, memory, gpus)

    return HardwareReport(
        detected_at=datetime.now(tz=UTC),
        os=os_info,
        cpu=cpu,
        memory=memory,
        gpus=gpus,
        volumes=volumes,
        tier=tier,
        warnings=warnings,
    )
