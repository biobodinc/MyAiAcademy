from __future__ import annotations

import platform

import psutil

from myai_core.hardware.models import CpuInfo


def probe_cpu() -> CpuInfo:
    info = CpuInfo(
        architecture=platform.machine() or None,
        physical_cores=psutil.cpu_count(logical=False),
        logical_threads=psutil.cpu_count(logical=True),
    )
    try:
        freq = psutil.cpu_freq()
        if freq and freq.max:
            info.max_frequency_mhz = float(freq.max)
    except (OSError, RuntimeError, AttributeError):
        pass
    info.model_name = _model_name()
    return info


def _model_name() -> str | None:
    # Optional dependency: py-cpuinfo gives a clean brand string on every OS.
    try:
        import cpuinfo

        brand = cpuinfo.get_cpu_info().get("brand_raw")
        if brand:
            return str(brand)
    except Exception:  # noqa: S110 - optional probe; any failure is acceptable
        pass
    # Fallbacks without extra dependencies.
    processor = platform.processor()
    if processor and processor not in {"x86_64", "AMD64", "arm64", "aarch64"}:
        return processor
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:  # noqa: PTH123
            for line in fh:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None
