"""Hardware detection must never crash and must not over-claim capability."""

from __future__ import annotations

import pytest

from myai_core.hardware import detect_hardware
from myai_core.hardware import gpu as gpu_mod
from myai_core.hardware._subprocess import ProbeUnavailableError
from myai_core.hardware.models import (
    AcceleratorBackend,
    CpuInfo,
    GpuInfo,
    GpuVendor,
    HardwareTier,
    MemoryInfo,
)
from myai_core.hardware.tiers import estimate_tier

GiB = 1024**3


def test_detect_never_raises_when_every_probe_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise RuntimeError("probe exploded")

    monkeypatch.setattr("myai_core.hardware.detect.probe_cpu", boom)
    monkeypatch.setattr("myai_core.hardware.detect.probe_memory", boom)
    monkeypatch.setattr("myai_core.hardware.detect.probe_os", boom)
    monkeypatch.setattr("myai_core.hardware.detect.probe_gpus", lambda: ([], ["gpu failed"]))
    monkeypatch.setattr("myai_core.hardware.detect.probe_volumes", lambda: ([], ["vol failed"]))

    report = detect_hardware()
    assert report.os.system == "unknown"
    assert report.cpu.physical_cores is None
    assert len(report.warnings) >= 5
    assert report.tier.tier is HardwareTier.ENTRY


def test_real_detection_smoke() -> None:
    report = detect_hardware()
    assert report.os.system
    assert report.memory.total_bytes and report.memory.total_bytes > 0
    assert report.tier.method == "specification-estimate"
    assert report.tier.benchmark_ran is False


def test_nvidia_smi_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = "0, NVIDIA GeForce RTX 4090, 24564, 1200, 560.35, 41, 3\n"
    monkeypatch.setattr(gpu_mod, "run_tool", lambda argv, **kw: sample)
    gpus = gpu_mod._probe_nvidia_smi()
    assert len(gpus) == 1
    g = gpus[0]
    assert g.vendor is GpuVendor.NVIDIA
    assert g.backend is AcceleratorBackend.CUDA
    assert g.vram_total_bytes == 24564 * 1024 * 1024
    assert g.temperature_c == 41.0
    assert g.driver_version == "560.35"


def test_gpu_probe_falls_through_when_tools_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(argv: list[str], **kw: object) -> str:
        raise ProbeUnavailableError(f"{argv[0]} not found")

    monkeypatch.setattr(gpu_mod, "run_tool", missing)

    def no_torch() -> list[object]:
        raise ProbeUnavailableError("no torch")

    monkeypatch.setattr(gpu_mod, "_probe_torch", no_torch)
    gpus, warnings = gpu_mod.probe_gpus()
    assert gpus == []
    # Missing tools are silent (normal), OS inventory failure is a warning.
    assert all("not found" in w for w in warnings)


def test_windows_adapter_ram_cap_is_treated_as_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = '[{"Name":"NVIDIA GeForce RTX 3080","AdapterRAM":4293918720,"DriverVersion":"31.0"}]'
    monkeypatch.setattr(gpu_mod, "run_tool", lambda argv, **kw: payload)
    (g,) = gpu_mod._probe_windows_cim()
    assert g.vram_total_bytes is None  # 4 GiB wrap: do not report a wrong number
    assert g.backend is AcceleratorBackend.NONE  # inventory only, no acceleration claimed
    assert g.vendor is GpuVendor.NVIDIA


def _gpu(vram_gib: float, backend: AcceleratorBackend = AcceleratorBackend.CUDA) -> GpuInfo:
    return GpuInfo(
        index=0, name="test", vram_total_bytes=int(vram_gib * GiB), backend=backend, source="t"
    )


@pytest.mark.parametrize(
    ("vram", "ram", "expected"),
    [
        (2, 32, HardwareTier.ENTRY),
        (6, 32, HardwareTier.BASIC),
        (8, 32, HardwareTier.CAPABLE),
        (12, 32, HardwareTier.CAPABLE),
        (16, 32, HardwareTier.POWERFUL),
        (24, 64, HardwareTier.WORKSTATION),
        (16, 8, HardwareTier.CAPABLE),  # low system RAM steps down one tier
    ],
)
def test_tier_thresholds(vram: float, ram: float, expected: HardwareTier) -> None:
    est = estimate_tier(
        CpuInfo(physical_cores=8), MemoryInfo(total_bytes=int(ram * GiB)), [_gpu(vram)]
    )
    assert est.tier is expected


def test_cpu_only_tiers() -> None:
    weak = estimate_tier(CpuInfo(physical_cores=4), MemoryInfo(total_bytes=16 * GiB), [])
    strong = estimate_tier(CpuInfo(physical_cores=16), MemoryInfo(total_bytes=64 * GiB), [])
    assert weak.tier is HardwareTier.ENTRY
    assert strong.tier is HardwareTier.BASIC


def test_unverified_gpu_does_not_raise_tier() -> None:
    inventory_only = GpuInfo(index=0, name="Some GPU", source="lspci")
    est = estimate_tier(
        CpuInfo(physical_cores=4), MemoryInfo(total_bytes=16 * GiB), [inventory_only]
    )
    assert est.tier is HardwareTier.ENTRY
    assert any("no compute backend" in r for r in est.rationale)


def test_size_string_parsing() -> None:
    assert gpu_mod._parse_size_string("8 GB") == 8 * GiB
    assert gpu_mod._parse_size_string("1536 MB") == 1536 * 1024**2
    assert gpu_mod._parse_size_string("n/a") is None
